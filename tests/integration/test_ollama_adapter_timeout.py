"""Adapter 25s timeout fires cleanly on runaway, FakeClock-driven.

Day 10 update: timeout is now exercised against the text-only translate()
path. The hanging mock is unchanged (real ollama.chat is sync; the
adapter wraps it via asyncio.to_thread) blocked on threading.Event.
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from integration._errors import InferenceTimeout
from integration.ollama_adapter import OllamaAdapter
from tests.fakes.fake_clock import FakeClock


class _HangingClient:
    """Sync chat() that blocks the asyncio.to_thread worker forever."""

    def __init__(self) -> None:
        self._block = threading.Event()  # never set — forces a hang

    def chat(self, **_kwargs: object) -> None:
        self._block.wait()


@pytest.mark.asyncio
async def test_adapter_timeout_fires_at_25s() -> None:
    clock = FakeClock()
    client = _HangingClient()
    adapter = OllamaAdapter(client=client, clock=clock, timeout_s=25.0)

    task = asyncio.create_task(adapter.translate("hola", "es"))
    # Two cycles, not one. The first sleep(0) lets `translate` run up to
    # `await self._call_with_timeout(...)`, which schedules the call task
    # and the timer task. The timer task itself hasn't yet executed its
    # body — it needs another loop cycle to call clock.sleep(25.0) and
    # enqueue into FakeClock.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(26.0)  # virtual time past the 25s ceiling

    with pytest.raises(InferenceTimeout, match=r"exceeded 25\.0s"):
        await task

    # Release the orphan worker thread so the test process exits cleanly.
    client._block.set()
