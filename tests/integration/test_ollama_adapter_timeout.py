"""Day-1 anchor test (test_strategy.md §8 #3): adapter 25s timeout fires
cleanly on runaway, FakeClock-driven, sub-millisecond wall clock.

If this regresses, KIN rediscovers the 39-minute Swahili runaway loop on
stage. The test deliberately uses a sync hanging mock (real ollama.chat
is sync; the adapter wraps it via asyncio.to_thread) blocked on
threading.Event — the same pattern proven in scripts/gemma_hello.py's
cancellation investigation.
"""

import asyncio
import threading
from pathlib import Path

import pytest

from integration.ollama_adapter import InferenceTimeout, OllamaAdapter
from tests.fakes.fake_clock import FakeClock


class _HangingClient:
    """Sync chat() that blocks the asyncio.to_thread worker forever.

    threading.Event().wait() blocks the OS thread (not a coroutine), which
    is the realistic analog of "ollama.chat is mid-HTTP and not returning
    yet." Matches scripts/gemma_hello.py:203-220.
    """

    def __init__(self) -> None:
        self._block = threading.Event()  # never set — forces a hang

    def chat(self, **_kwargs: object) -> None:
        self._block.wait()


@pytest.mark.asyncio
async def test_adapter_timeout_fires_at_25s(tmp_path: Path) -> None:
    audio = tmp_path / "stub.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")  # placeholder; preprocess mocked

    clock = FakeClock()
    client = _HangingClient()
    adapter = OllamaAdapter(client=client, clock=clock, timeout_s=25.0)

    # This test exercises the Ollama timeout race, NOT the padding branch.
    # Bypass real ffmpeg with a byte-copy lambda so the test stays orthogonal
    # to ffmpeg presence/absence. Padding branch tests live in
    # test_ollama_adapter_padding.py (Session 1B).
    adapter._preprocess = lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())  # type: ignore[method-assign]

    task = asyncio.create_task(adapter.transcribe(audio))
    # Two cycles, not one. The first sleep(0) lets `transcribe` run up to
    # `await self._call_with_timeout(...)`, which schedules the call task
    # and the timer task. The timer task itself hasn't yet executed its
    # body — it needs another loop cycle to call clock.sleep(25.0) and
    # enqueue into FakeClock. Without the second cycle, tick(26) finds an
    # empty queue and the test hangs because the worker thread is
    # blocked while the timer never wakes. (The §5 strategy doc's
    # single-sleep example is correct for an async-client shape, but our
    # adapter does sync setup before the race.)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(26.0)  # virtual time past the 25s ceiling

    with pytest.raises(InferenceTimeout, match=r"exceeded 25\.0s"):
        await task

    # Release the orphan worker thread so the test process exits cleanly.
    # The Day-4 finding stands: cancellation only bounds Core time. We've
    # observed the timeout fire; releasing here is hygiene, not part of
    # the assertion.
    client._block.set()
