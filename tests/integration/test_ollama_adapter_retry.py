"""GGML retry coverage for OllamaAdapter.translate().

Day 10 update: retry policy unchanged — still catches
ollama.ResponseError / ollama.RequestError on the first call, retries
once, raises InferenceFailed if both fail. InferenceTimeout still
propagates without being caught by the retry.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import ollama
import pytest

from integration._errors import InferenceFailed, InferenceTimeout
from integration.ollama_adapter import OllamaAdapter
from tests.fakes.fake_clock import FakeClock


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Response:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.eval_count = 10
        self.done_reason = "stop"
        self.prompt_eval_count = 20
        self.load_duration = 1_000_000


class _RetryStubClient:
    """Sync chat() that raises ollama.ResponseError on the first N calls,
    then returns a configured response. If `success_response` is None,
    keeps raising forever.
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


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt() -> None:
    """First chat() raises; second returns a clean translation. call_count == 2."""
    client = _RetryStubClient(raise_first_n=1, success_response=_Response("hello"))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    result = await adapter.translate("hola", "es")

    assert client.call_count == 2
    assert result == "hello"


@pytest.mark.asyncio
async def test_retry_failure_raises_inference_failed() -> None:
    client = _RetryStubClient(raise_first_n=2, success_response=None)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with pytest.raises(InferenceFailed, match=r"after retry"):
        await adapter.translate("hola", "es")

    assert client.call_count == 2


class _HangingClient:
    """Sync chat() that blocks the asyncio.to_thread worker forever."""

    def __init__(self) -> None:
        self._block = threading.Event()
        self.call_count = 0

    def chat(self, **_kwargs: object) -> None:
        self.call_count += 1
        self._block.wait()


@pytest.mark.asyncio
async def test_retry_does_not_catch_timeout() -> None:
    """Boundary test: the retry's except clause is type-specific
    (ollama.ResponseError, ollama.RequestError). InferenceTimeout
    must propagate cleanly without triggering retry.
    """
    clock = FakeClock()
    client = _HangingClient()
    adapter = OllamaAdapter(client=client, clock=clock, timeout_s=25.0)

    task = asyncio.create_task(adapter.translate("hola", "es"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(26.0)

    with pytest.raises(InferenceTimeout):
        await task

    assert client.call_count == 1

    client._block.set()  # release orphan worker thread
