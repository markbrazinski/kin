"""Two-stage pipeline: Whisper ASR → Gemma translation → TranscriptionResult.

Seven tests covering happy path, English short-circuit, ordering,
data-flow, and exception propagation in both directions.

Adapter stubs are duck-typed — the pipeline accepts anything with
.transcribe / .translate. We deliberately don't construct real
WhisperAdapter / OllamaAdapter here; their error classes are imported
solely to assert the pipeline propagates them unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integration._errors import InferenceTimeout
from integration.transcription_pipeline import (
    PipelineMetrics,
    transcribe_and_translate,
    transcribe_and_translate_with_metrics,
)
from integration.whisper_adapter import PaddingFailed


class _WhisperStub:
    def __init__(self, text: str = "hola") -> None:
        self._text = text
        self.calls: list[tuple[Path, str]] = []

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        self.calls.append((audio_path, lang))
        return self._text


class _OllamaStub:
    def __init__(self, english: str = "hello") -> None:
        self._english = english
        self.calls: list[tuple[str, str]] = []

    async def translate(self, text: str, source_lang: str) -> str:
        self.calls.append((text, source_lang))
        return self._english


class _RaisingWhisper:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.call_count = 0

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        self.call_count += 1
        raise self._error


class _RaisingOllama:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.call_count = 0

    async def translate(self, text: str, source_lang: str) -> str:
        self.call_count += 1
        raise self._error


@pytest.mark.asyncio
async def test_pipeline_returns_validated_transcription_result(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _WhisperStub(text="hola")
    ollama = _OllamaStub(english="hello")

    result = await transcribe_and_translate(
        audio, "es", whisper=whisper, ollama=ollama
    )

    assert result.transcription == "hola"
    assert result.english_translation == "hello"


@pytest.mark.asyncio
async def test_pipeline_calls_whisper_then_ollama_in_order(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    order: list[str] = []

    class _OrderedWhisper:
        async def transcribe(self, audio_path: Path, lang: str) -> str:
            order.append("whisper")
            return "hola"

    class _OrderedOllama:
        async def translate(self, text: str, source_lang: str) -> str:
            order.append("ollama")
            return "hello"

    await transcribe_and_translate(
        audio, "es", whisper=_OrderedWhisper(), ollama=_OrderedOllama()
    )

    assert order == ["whisper", "ollama"]


@pytest.mark.asyncio
async def test_pipeline_passes_source_text_into_translate(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _WhisperStub(text="¿Puedo tener sal?")
    ollama = _OllamaStub(english="Can I have salt?")

    await transcribe_and_translate(
        audio, "es", whisper=whisper, ollama=ollama
    )

    assert ollama.calls == [("¿Puedo tener sal?", "es")]


@pytest.mark.asyncio
async def test_pipeline_english_skips_gemma(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _WhisperStub(text="Hello, my name is Mark.")
    ollama = _OllamaStub(english="should not be used")

    result, metrics = await transcribe_and_translate_with_metrics(
        audio, "en", whisper=whisper, ollama=ollama
    )

    assert ollama.calls == []
    assert result.transcription == "Hello, my name is Mark."
    assert result.english_translation == "Hello, my name is Mark."
    assert isinstance(metrics, PipelineMetrics)
    assert metrics.skipped_translation is True
    assert metrics.gemma_latency_s == 0.0


@pytest.mark.asyncio
async def test_pipeline_propagates_whisper_padding_failure(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _RaisingWhisper(error=PaddingFailed("ffmpeg exit=1"))
    ollama = _OllamaStub()

    with pytest.raises(PaddingFailed):
        await transcribe_and_translate(
            audio, "es", whisper=whisper, ollama=ollama
        )

    assert whisper.call_count == 1
    assert ollama.calls == []


@pytest.mark.asyncio
async def test_pipeline_propagates_ollama_inference_timeout(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _WhisperStub(text="hola")
    ollama = _RaisingOllama(error=InferenceTimeout("translate timed out"))

    with pytest.raises(InferenceTimeout):
        await transcribe_and_translate(
            audio, "es", whisper=whisper, ollama=ollama
        )

    assert ollama.call_count == 1


@pytest.mark.asyncio
async def test_pipeline_propagates_whisper_inference_timeout(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")

    whisper = _RaisingWhisper(error=InferenceTimeout("whisper timed out"))
    ollama = _OllamaStub()

    with pytest.raises(InferenceTimeout):
        await transcribe_and_translate(
            audio, "es", whisper=whisper, ollama=ollama
        )

    assert whisper.call_count == 1
    assert ollama.calls == []
