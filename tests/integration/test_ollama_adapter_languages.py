"""Language-routing + lang-parameter tests for OllamaAdapter.

Day 7 Session 1 landed Spanish + the lang parameter; Day 7 Session 2
extends coverage to Arabic + Farsi, completing the §7 Locked set.

Five stub tests cover the lang parameter:

  1. lang='es' routes through the prompt builder with "Spanish" in
     the captured content and the rest of the pipeline (validation,
     base64 encode, response unwrap) still works.
  2. lang='klingon' (a non-SupportedLang value) raises
     UnsupportedLanguage BEFORE any preprocessing or inference
     attempt — call_count stays at 0.
  3. Default lang (no kwarg) still produces a working English path
     with "English" in the captured prompt — regression guard.
  4. lang='ar' routes with "Arabic" in the captured prompt.
  5. lang='fa' routes with "Persian" in the captured prompt
     (LANGUAGE_NAMES['fa'] = "Persian (Farsi)").

The _CapturingStubClient extends the validation test's stub pattern
to record the messages kwarg passed to chat(), so we can assert on
prompt content. _preprocess is monkeypatched to a byte-copy lambda
so tests don't shell out to ffmpeg (mirrors
test_ollama_adapter_validation.py:81).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from integration.ollama_adapter import (
    OllamaAdapter,
    UnsupportedLanguage,
)


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Response:
    """Duck-typed Ollama response — same shape as the validation test."""

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


_VALID_PAYLOAD = json.dumps({"transcription": "hola", "english_translation": "hello"})


def _bypass_ffmpeg(adapter: OllamaAdapter) -> None:
    """Mirror of test_ollama_adapter_validation.py:81 — copy bytes
    instead of shelling out to ffmpeg.
    """
    adapter._preprocess = (  # type: ignore[method-assign]
        lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())
    )


@pytest.mark.asyncio
async def test_spanish_routes_with_spanish_language_name_in_prompt(
    tmp_path: Path,
) -> None:
    """lang='es' → prompt mentions 'Spanish' and inference proceeds."""
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _CapturingStubClient(_Response(_VALID_PAYLOAD))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    result = await adapter.transcribe(audio, lang="es")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Spanish" in client.last_messages[0]["content"]
    assert result.transcription == "hola"
    assert result.english_translation == "hello"


@pytest.mark.asyncio
async def test_invalid_language_raises_before_inference(
    tmp_path: Path,
) -> None:
    """lang='klingon' raises UnsupportedLanguage; chat() never invoked.

    'klingon' is not a SupportedLang value at all (vs Session 1
    where 'ar' was in SupportedLang but not yet in IMPLEMENTED_LANGS).
    After Day 7 Session 2 all four §7-Locked languages are
    implemented, so the regression guard now exercises the broader
    case: any string outside SupportedLang must trip the same raise
    path.
    """
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _CapturingStubClient(_Response(_VALID_PAYLOAD))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    with pytest.raises(UnsupportedLanguage):
        await adapter.transcribe(audio, lang="klingon")

    assert client.call_count == 0


@pytest.mark.asyncio
async def test_english_default_still_works(tmp_path: Path) -> None:
    """No lang argument → defaults to 'en'; prompt mentions 'English'."""
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _CapturingStubClient(_Response(_VALID_PAYLOAD))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    result = await adapter.transcribe(audio)

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "English" in client.last_messages[0]["content"]
    assert result.transcription == "hola"


@pytest.mark.asyncio
async def test_arabic_routes_with_arabic_language_name_in_prompt(
    tmp_path: Path,
) -> None:
    """lang='ar' → prompt mentions 'Arabic' and inference proceeds."""
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _CapturingStubClient(_Response(_VALID_PAYLOAD))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    result = await adapter.transcribe(audio, lang="ar")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Arabic" in client.last_messages[0]["content"]
    assert result.transcription == "hola"
    assert result.english_translation == "hello"


@pytest.mark.asyncio
async def test_farsi_routes_with_persian_language_name_in_prompt(
    tmp_path: Path,
) -> None:
    """lang='fa' → prompt mentions 'Persian' and inference proceeds.

    LANGUAGE_NAMES['fa'] is 'Persian (Farsi)'. The substring
    assertion targets 'Persian' (the canonical leading word) so
    the test survives if the parenthetical is ever dropped.
    """
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _CapturingStubClient(_Response(_VALID_PAYLOAD))
    adapter = OllamaAdapter(client=client, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    result = await adapter.transcribe(audio, lang="fa")

    assert client.call_count == 1
    assert client.last_messages is not None
    assert "Persian" in client.last_messages[0]["content"]
    assert result.transcription == "hola"
    assert result.english_translation == "hello"
