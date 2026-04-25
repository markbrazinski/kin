"""Clock Protocol for deterministic time; implementations live in Integration."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Monotonic clock + cancellable async sleep.

    Core has no I/O; this is an interface. Integration provides the
    real adapter (SystemClock); tests provide a FakeClock. Adapters
    receive a Clock via constructor injection so the 25s ollama_adapter
    timeout can be exercised against FakeClock without spending
    wall-clock seconds.
    """

    def monotonic(self) -> float:
        """Return monotonic seconds since an arbitrary epoch.

        Monotonic is correct for measuring elapsed time; wall-clock
        changes must not move it backward.
        """
        ...

    async def sleep(self, seconds: float) -> None:
        """Asynchronously pause for `seconds` seconds.

        Cancellable: callers race sleeps against other awaitables via
        asyncio.wait / task.cancel (see docs/test_strategy.md §5).
        """
        ...
