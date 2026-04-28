"""Deterministic FakeClock for async tests — satisfies core.clock.Clock."""

import asyncio
import heapq
from datetime import datetime, timedelta, timezone
from itertools import count


_DEFAULT_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Deterministic clock for async tests.

    Call `await clock.tick(seconds)` to advance virtual time. Any
    coroutine awaiting `clock.sleep(x)` resumes when accumulated ticks
    reach x. Zero wall-clock time elapses; the adapter 25s timeout
    test runs in ~5ms instead of 25 seconds.

    Wall-clock now() is independent of monotonic ticks: storage tests
    that need distinct timestamps across writes call advance_now() or
    set_now() between operations. Default start: 2026-04-29T12:00:00Z.
    """

    def __init__(
        self,
        start: float = 0.0,
        start_now: datetime = _DEFAULT_NOW,
    ) -> None:
        self._now = start
        self._now_wall = start_now
        self._queue: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq = count()

    def monotonic(self) -> float:
        return self._now

    def now(self) -> datetime:
        return self._now_wall

    def set_now(self, dt: datetime) -> None:
        """Set wall-clock time explicitly. Must be tz-aware."""
        if dt.tzinfo is None:
            raise ValueError("FakeClock.set_now requires tz-aware datetime")
        self._now_wall = dt

    def advance_now(self, seconds: float) -> None:
        """Advance wall-clock time by `seconds` (independent of monotonic)."""
        self._now_wall = self._now_wall + timedelta(seconds=seconds)

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        heapq.heappush(self._queue, (self._now + seconds, next(self._seq), fut))
        try:
            await fut
        except asyncio.CancelledError:
            self._queue = [e for e in self._queue if e[2] is not fut]
            heapq.heapify(self._queue)
            raise

    async def tick(self, seconds: float) -> None:
        """Advance virtual time, waking sleepers whose deadlines have passed."""
        target = self._now + seconds
        while self._queue and self._queue[0][0] <= target:
            wake_at, _, fut = heapq.heappop(self._queue)
            self._now = wake_at
            if not fut.done():
                fut.set_result(None)
            await asyncio.sleep(0)
        self._now = target
        await asyncio.sleep(0)
