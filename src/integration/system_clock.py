"""Real Clock implementation wrapping time.monotonic and asyncio.sleep."""

import asyncio
import time

from core.clock import Clock


class SystemClock:
    """Clock Protocol impl backed by time.monotonic + asyncio.sleep.

    monotonic() uses time.monotonic because the ollama_adapter 25s
    timeout needs a clock that never goes backward when wall-clock
    changes (NTP, DST, user retime). asyncio.sleep is the async-aware
    pause for adapters that race sleeps against inference tasks via
    asyncio.wait.
    """

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


SYSTEM_CLOCK: Clock = SystemClock()
"""Module-level singleton, typed as Clock so callers bind to the Protocol."""
