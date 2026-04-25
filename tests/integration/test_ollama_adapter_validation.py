"""InvalidToolCall coverage for OllamaAdapter (Day 5 Session 1B).

Two parametrized cases — both load-bearing:

  1. Raw garbage content. Exercises the bare ValidationError path.
  2. Fence-wrapped malformed JSON. Exercises _strip_json_fences()
     wired into the validation flow; without the helper, this case
     would never reach the JSON parser at all.

Adapter is constructed with the default SystemClock and a
generous 10s timeout. The sync stub returns in microseconds, so the
call task always wins the race; FakeClock+threading scheduling would
add complexity without buying determinism for a non-timeout test.
"""

from pathlib import Path
from typing import Any

import pytest

from integration.ollama_adapter import InvalidToolCall, OllamaAdapter


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Response:
    """Duck-typed Ollama response: message.content + metric attrs the
    adapter reads via getattr in the inference_complete payload.
    """

    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.eval_count = 10
        self.done_reason = "stop"
        self.prompt_eval_count = 20
        self.load_duration = 1_000_000  # nanoseconds, per Ollama SDK


class _StubClient:
    """Sync chat() that returns a pre-configured response."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.call_count = 0

    def chat(self, **_kwargs: object) -> Any:
        self.call_count += 1
        return self._response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_content",
    [
        pytest.param("this is not json at all", id="raw-garbage"),
        pytest.param(
            "```json\n{broken json content\n```",
            id="fence-wrapped-malformed",
        ),
    ],
)
async def test_invalid_tool_call_on_malformed_json(
    tmp_path: Path, raw_content: str
) -> None:
    """Malformed Gemma output → ValidationError → InvalidToolCall.

    The fence-wrapped case is what proves _strip_json_fences() is wired
    into the validation flow; without the strip, the fence helper would
    have no integration coverage at all.
    """
    audio = tmp_path / "stub.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _StubClient(_Response(raw_content))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    # Bypass real ffmpeg — this test exercises the validation branch only.
    adapter._preprocess = lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())  # type: ignore[method-assign]

    with pytest.raises(InvalidToolCall, match=r"validation"):
        await adapter.transcribe(audio)

    assert client.call_count == 1
