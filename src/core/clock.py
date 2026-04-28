"""Clock Protocol for deterministic time; implementations live in Integration."""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Monotonic + wall-clock time + cancellable async sleep.

    Core has no I/O; this is an interface. Integration provides the
    real adapter (SystemClock); tests provide a FakeClock. Adapters
    receive a Clock via constructor injection so the 25s ollama_adapter
    timeout can be exercised against FakeClock without spending
    wall-clock seconds, and so storage timestamps are deterministic
    in tests.

    `monotonic()` is for elapsed-time math (the timeout race).
    `now()` is for wall-clock timestamps (storage created_at /
    updated_at, audit_event.at). Storage uses the latter.
    """

    def monotonic(self) -> float:
        """Return monotonic seconds since an arbitrary epoch.

        Monotonic is correct for measuring elapsed time; wall-clock
        changes must not move it backward.
        """
        ...

    def now(self) -> datetime:
        """Return wall-clock time as a tz-aware UTC datetime.

        For storage timestamps and audit events. Must be tz-aware so
        ISO-8601 serialization round-trips cleanly through Pydantic.
        """
        ...

    async def sleep(self, seconds: float) -> None:
        """Asynchronously pause for `seconds` seconds.

        Cancellable: callers race sleeps against other awaitables via
        asyncio.wait / task.cancel (see docs/test_strategy.md §5).
        """
        ...
