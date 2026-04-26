"""Language-routing tests for OllamaAdapter.translate().

Day 10 update: the language-aware prompt now wraps a translation
request rather than an audio transcription request. Five tests cover
the lang parameter:

  1. source_lang='es' routes through with "Spanish" in the captured prompt.
  2. source_lang='klingon' raises UnsupportedLanguage; chat() never invoked.
  3. source_lang='en' produces an "English" prompt (regression guard;
     pipeline short-circuits English in the orchestration layer, but
     adapter still accepts en for completeness).
  4. source_lang='ar' routes with "Arabic" in the prompt.
  5. source_lang='fa' routes with "Persian" in the prompt.
"""

from __future__ import annotations

from typing import Any

import pytest

from integration.ollama_adapter import OllamaAdapter, UnsupportedLanguage


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Response:
    """Duck-typed Ollama response."""

    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.eval_count = 10
        self.done_reason = "stop"
        self.prompt_eval_count = 20
        self.load_duration = 1_000_000


class _CapturingStubClient:
    """Sync chat() that captures `messages` for prompt-content assertion."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.call_count = 0
        self.last_messages: list[dict[str, Any]] | None = None

    def chat(self, **kwargs: object) -> Any:
        self.call_count += 1
        self.last_messages = kwargs.get("messages")  # type: ignore[assignment]
        return self._response


_TRANSLATION = "hello"


@pytest.mark.asyncio
async def test_spanish_routes_with_spanish_language_name_in_prompt() -> None:
    client = _CapturingStubClient(_Response(_TRANSLATION))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    result = await adapter.translate("hola", "es")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Spanish" in client.last_messages[0]["content"]
    assert "hola" in client.last_messages[0]["content"]
    assert result == _TRANSLATION


@pytest.mark.asyncio
async def test_invalid_language_raises_before_inference() -> None:
    client = _CapturingStubClient(_Response(_TRANSLATION))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    with pytest.raises(UnsupportedLanguage):
        await adapter.translate("foo", "klingon")

    assert client.call_count == 0


@pytest.mark.asyncio
async def test_english_routes_with_english_language_name_in_prompt() -> None:
    """source_lang='en' is a valid call — adapter doesn't short-circuit;
    the pipeline does. Adapter just routes the prompt through.
    """
    client = _CapturingStubClient(_Response(_TRANSLATION))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    result = await adapter.translate("hello world", "en")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "English" in client.last_messages[0]["content"]
    assert result == _TRANSLATION


@pytest.mark.asyncio
async def test_arabic_routes_with_arabic_language_name_in_prompt() -> None:
    client = _CapturingStubClient(_Response(_TRANSLATION))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    result = await adapter.translate("مرحبا", "ar")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Arabic" in client.last_messages[0]["content"]
    assert result == _TRANSLATION


@pytest.mark.asyncio
async def test_farsi_routes_with_persian_language_name_in_prompt() -> None:
    """LANGUAGE_NAMES['fa'] is 'Persian (Farsi)'."""
    client = _CapturingStubClient(_Response(_TRANSLATION))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)

    result = await adapter.translate("سلام", "fa")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Persian" in client.last_messages[0]["content"]
    assert result == _TRANSLATION
