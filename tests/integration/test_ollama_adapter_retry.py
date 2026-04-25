"""GGML retry coverage for OllamaAdapter (Day 6 Session 2).

Closes the adapter chapter — InferenceFailed gets direct test coverage
via monkeypatched ollama.chat raising ollama.ResponseError. Q1 of the
Day 6 opening locked option (b): test the retry without forcing a
real GGML crash.

Three tests:
  1. Retry succeeds on second attempt (call_count == 2, success).
  2. Retry fails on second attempt → InferenceFailed (call_count == 2).
  3. InferenceTimeout is NOT caught by the retry mechanism
     (boundary test; protects against future lazy `except Exception`).
"""

import asyncio
import threading
from pathlib import Path
from typing import Any

import ollama
import pytest

from integration.ollama_adapter import (
    InferenceFailed,
    InferenceTimeout,
    OllamaAdapter,
)
from tests.fakes.fake_clock import FakeClock


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Response:
    """Minimal duck-typed Ollama response for happy-path success."""

    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.eval_count = 10
        self.done_reason = "stop"
        self.prompt_eval_count = 20
        self.load_duration = 1_000_000


class _RetryStubClient:
    """Sync chat() that raises ollama.ResponseError on the first N
    calls, then returns a configured response. If `success_response`
    is None, keeps raising forever — useful for the
    retry-fails-on-both-attempts case.
    """

    def __init__(self, raise_first_n: int, success_response: Any | None) -> None:
        self._raise_first_n = raise_first_n
        self._success = success_response
        self.call_count = 0

    def chat(self, **_kwargs: object) -> Any:
        self.call_count += 1
        if self.call_count <= self._raise_first_n:
            raise ollama.ResponseError("simulated GGML failure", status_code=500)
        if self._success is None:
            raise ollama.ResponseError("no success configured", status_code=500)
        return self._success


_VALID_JSON = '{"transcription": "hola", "english_translation": "hi"}'


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(tmp_path: Path) -> None:
    """First chat() raises ollama.ResponseError; second returns valid
    JSON. Adapter retries once, succeeds, validates, and returns the
    TranscriptionResult. call_count must be exactly 2.
    """
    audio = tmp_path / "stub.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _RetryStubClient(raise_first_n=1, success_response=_Response(_VALID_JSON))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    adapter._preprocess = lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())  # type: ignore[method-assign]

    result = await adapter.transcribe(audio)

    assert client.call_count == 2
    assert result.transcription == "hola"
    assert result.english_translation == "hi"


@pytest.mark.asyncio
async def test_retry_failure_raises_inference_failed(tmp_path: Path) -> None:
    """Both attempts raise ollama.ResponseError. Adapter retries once,
    second attempt also fails, InferenceFailed surfaces with the
    retry error chained.
    """
    audio = tmp_path / "stub.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _RetryStubClient(raise_first_n=2, success_response=None)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    adapter._preprocess = lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())  # type: ignore[method-assign]

    with pytest.raises(InferenceFailed, match=r"after retry"):
        await adapter.transcribe(audio)

    assert client.call_count == 2


class _HangingClient:
    """Sync chat() that blocks the asyncio.to_thread worker forever.
    Same shape as test_ollama_adapter_timeout.py's _HangingClient.
    """

    def __init__(self) -> None:
        self._block = threading.Event()
        self.call_count = 0

    def chat(self, **_kwargs: object) -> None:
        self.call_count += 1
        self._block.wait()


@pytest.mark.asyncio
async def test_retry_does_not_catch_timeout(tmp_path: Path) -> None:
    """Boundary test: the retry's except clause is type-specific
    (ollama.ResponseError, ollama.RequestError). InferenceTimeout
    must propagate cleanly without triggering retry. If a future
    refactor changes the catch to `except Exception`, this test
    fails.
    """
    audio = tmp_path / "stub.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    clock = FakeClock()
    client = _HangingClient()
    adapter = OllamaAdapter(client=client, clock=clock, timeout_s=25.0)
    adapter._preprocess = lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())  # type: ignore[method-assign]

    task = asyncio.create_task(adapter.transcribe(audio))
    # Same two-cycle warm-up as the Session 1A timeout test:
    # transcribe() does sync setup before reaching the timeout race;
    # one cycle scheduling, one cycle for timer body to enqueue.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(26.0)

    with pytest.raises(InferenceTimeout):
        await task

    # Critical assertion: only ONE chat attempt. If the retry caught
    # InferenceTimeout, call_count would be 2 (or higher).
    assert client.call_count == 1

    client._block.set()  # release orphan worker thread
