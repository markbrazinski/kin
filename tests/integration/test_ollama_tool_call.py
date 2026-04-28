"""Tool-calling coverage for OllamaAdapter.tool_call().

Mirrors stub patterns from test_ollama_adapter_retry.py /
test_ollama_adapter_timeout.py. Eight tests cover happy path, four
InvalidToolCall failure modes, FakeClock timeout, and the retry-once
contract (success + failure).

Wire-format contract (Apr 28 hello-world + Apr 29 multilang sweep):
response.message.tool_calls is list | None. Each item exposes
.function.name (str) and .function.arguments (already-parsed dict).
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import ollama
import pytest
import structlog

from core.tool_calling import ToolCallResult
from integration._errors import InferenceFailed, InferenceTimeout, InvalidToolCall
from integration.extraction_tools import EXTRACT_INTAKE_FIELDS_TOOL
from integration.ollama_adapter import OllamaAdapter
from tests.fakes.fake_clock import FakeClock


# ─── Stub object graph (mirrors test_ollama_adapter_retry.py) ─────


class _ToolFn:
    def __init__(self, name: str, arguments: Any) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, function: _ToolFn) -> None:
        self.function = function


class _ToolMsg:
    def __init__(
        self,
        content: str = "",
        tool_calls: list[_ToolCall] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _ToolResponse:
    """Duck-typed Ollama chat response with tool_calls."""

    def __init__(
        self,
        tool_calls: list[_ToolCall] | None = None,
        content: str = "",
    ) -> None:
        self.message = _ToolMsg(content=content, tool_calls=tool_calls)
        self.eval_count = 27
        self.done_reason = "stop"
        self.prompt_eval_count = 200
        self.load_duration = 1_000_000


def _carlos_response() -> _ToolResponse:
    """A canonical valid response matching the Apr 28 hello-world output."""
    return _ToolResponse(
        tool_calls=[
            _ToolCall(
                function=_ToolFn(
                    name="extract_intake_fields",
                    arguments={"full_name": "Carlos", "relationship": "son"},
                )
            )
        ]
    )


# ─── Stub clients ─────────────────────────────────────────────────


class _ToolStubClient:
    """chat() returns a configured response; captures kwargs for assertion."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.call_count = 0
        self.last_kwargs: dict[str, Any] | None = None

    def chat(self, **kwargs: Any) -> Any:
        self.call_count += 1
        self.last_kwargs = kwargs
        return self._response


class _RetryToolStubClient:
    """Raises ollama.ResponseError on first N calls, then returns success."""

    def __init__(self, raise_first_n: int, success_response: Any | None) -> None:
        self._raise_first_n = raise_first_n
        self._success = success_response
        self.call_count = 0

    def chat(self, **_kwargs: Any) -> Any:
        self.call_count += 1
        if self.call_count <= self._raise_first_n:
            raise ollama.ResponseError("simulated GGML failure", status_code=500)
        if self._success is None:
            raise ollama.ResponseError("no success configured", status_code=500)
        return self._success


class _HangingClient:
    """chat() blocks the asyncio.to_thread worker forever."""

    def __init__(self) -> None:
        self._block = threading.Event()
        self.call_count = 0

    def chat(self, **_kwargs: Any) -> None:
        self.call_count += 1
        self._block.wait()


# ─── 1. Happy path ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_call_success_returns_result_with_name_and_arguments() -> None:
    client = _ToolStubClient(_carlos_response())
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with structlog.testing.capture_logs() as cap_logs:
        result = await adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )

    assert isinstance(result, ToolCallResult)
    assert result.name == "extract_intake_fields"
    assert result.arguments == {"full_name": "Carlos", "relationship": "son"}

    # SDK invocation contract.
    assert client.call_count == 1
    assert client.last_kwargs is not None
    assert client.last_kwargs["tools"] == [EXTRACT_INTAKE_FIELDS_TOOL]
    assert client.last_kwargs["think"] is False

    events = [log["event"] for log in cap_logs]
    assert "tool_call_invoked" in events
    assert "tool_call_returned" in events


# ─── 2-5. InvalidToolCall failure modes ───────────────────────────


@pytest.mark.asyncio
async def test_tool_call_empty_tool_calls_raises_invalid_tool_call() -> None:
    client = _ToolStubClient(_ToolResponse(tool_calls=None))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with structlog.testing.capture_logs() as cap_logs:
        with pytest.raises(InvalidToolCall, match="no tool calls"):
            await adapter.tool_call(
                messages=[{"role": "user", "content": "hola"}],
                tools=[EXTRACT_INTAKE_FIELDS_TOOL],
            )

    events = [log["event"] for log in cap_logs]
    assert "tool_call_no_tools_emitted" in events


@pytest.mark.asyncio
async def test_tool_call_name_mismatch_raises_invalid_tool_call() -> None:
    bad_response = _ToolResponse(
        tool_calls=[
            _ToolCall(function=_ToolFn(name="some_other_tool", arguments={}))
        ]
    )
    client = _ToolStubClient(bad_response)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with pytest.raises(InvalidToolCall, match="some_other_tool"):
        await adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )


@pytest.mark.asyncio
async def test_tool_call_malformed_structure_raises_invalid_tool_call() -> None:
    """tool_call missing the .function attribute entirely."""

    class _BareToolCall:
        pass

    bad_response = _ToolResponse(tool_calls=[_BareToolCall()])  # type: ignore[list-item]
    client = _ToolStubClient(bad_response)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with pytest.raises(InvalidToolCall, match="missing function"):
        await adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )


@pytest.mark.asyncio
async def test_tool_call_arguments_not_dict_raises_invalid_tool_call() -> None:
    bad_response = _ToolResponse(
        tool_calls=[
            _ToolCall(
                function=_ToolFn(
                    name="extract_intake_fields",
                    arguments="this should be a dict",
                )
            )
        ]
    )
    client = _ToolStubClient(bad_response)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with pytest.raises(InvalidToolCall, match="not a dict"):
        await adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )


# ─── 6. Timeout ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_call_timeout_raises_inference_timeout() -> None:
    clock = FakeClock()
    client = _HangingClient()
    adapter = OllamaAdapter(client=client, clock=clock, timeout_s=25.0)

    task = asyncio.create_task(
        adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )
    )
    # Same two-cycle dance as test_ollama_adapter_timeout.py.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(26.0)

    with pytest.raises(InferenceTimeout, match=r"exceeded 25\.0s"):
        await task

    client._block.set()  # release orphan worker thread


# ─── 7-8. Retry-once contract ─────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_call_retry_once_succeeds() -> None:
    client = _RetryToolStubClient(raise_first_n=1, success_response=_carlos_response())
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with structlog.testing.capture_logs() as cap_logs:
        result = await adapter.tool_call(
            messages=[{"role": "user", "content": "hola"}],
            tools=[EXTRACT_INTAKE_FIELDS_TOOL],
        )

    assert client.call_count == 2
    assert result.name == "extract_intake_fields"

    events = [log["event"] for log in cap_logs]
    assert "ggml_retry_attempted" in events


@pytest.mark.asyncio
async def test_tool_call_retry_once_then_fails_raises_inference_failed() -> None:
    client = _RetryToolStubClient(raise_first_n=2, success_response=None)
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with structlog.testing.capture_logs() as cap_logs:
        with pytest.raises(InferenceFailed, match="after retry"):
            await adapter.tool_call(
                messages=[{"role": "user", "content": "hola"}],
                tools=[EXTRACT_INTAKE_FIELDS_TOOL],
            )

    assert client.call_count == 2

    events = [log["event"] for log in cap_logs]
    assert "inference_failed_after_retry" in events
