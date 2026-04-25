"""Deterministic FakeClock for async tests — satisfies core.clock.Clock."""

import asyncio
import heapq
from itertools import count


class FakeClock:
    """Deterministic clock for async tests.

    Call `await clock.tick(seconds)` to advance virtual time. Any
    coroutine awaiting `clock.sleep(x)` resumes when accumulated ticks
    reach x. Zero wall-clock time elapses; the adapter 25s timeout
    test runs in ~5ms instead of 25 seconds.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = start
        self._queue: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq = count()

    def monotonic(self) -> float:
        return self._now

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
