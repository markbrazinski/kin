"""WhisperAdapter coverage — mirrors test_ollama_adapter_* patterns.

Eight tests:
  1. Concatenated source-language text from segment iterator.
  2. lang argument routes through to model.transcribe(language=...).
  3. Unsupported language raises before any model call.
  4. ffmpeg missing → PaddingUnavailable.
  5. Invalid audio bytes → PaddingFailed.
  6. Hanging model + FakeClock → InferenceTimeout at the configured ceiling.
  7. Non-timeout exception inside model.transcribe → InferenceFailed.
  8. inference_complete structlog event carries the per-call metrics.

The hang test uses a sync threading.Event-blocked stub; same pattern as
test_ollama_adapter_timeout.py and test_ollama_adapter_retry.py.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog

from integration._errors import InferenceFailed, InferenceTimeout
from integration.whisper_adapter import (
    PaddingFailed,
    PaddingUnavailable,
    UnsupportedLanguage,
    WhisperAdapter,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_whisper_model import (
    FakeInfo,
    FakeSegment,
    FakeWhisperModel,
    RaisingWhisperModel,
)


def _bypass_ffmpeg(adapter: WhisperAdapter) -> None:
    """Copy bytes instead of shelling out to ffmpeg."""
    adapter._preprocess = (  # type: ignore[method-assign]
        lambda src, dst, **_kw: dst.write_bytes(src.read_bytes())
    )


@pytest.mark.asyncio
async def test_whisper_returns_concatenated_source_text(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    model = FakeWhisperModel(segments=["Hola, ", "me llamo ", "Sarah."])
    adapter = WhisperAdapter(model=model, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    text = await adapter.transcribe(audio, lang="es")

    assert text == "Hola, me llamo Sarah."
    assert model.call_count == 1


@pytest.mark.asyncio
async def test_whisper_passes_language_to_model_transcribe(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    model = FakeWhisperModel(segments=["hola"])
    adapter = WhisperAdapter(model=model, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    await adapter.transcribe(audio, lang="es")

    assert model.last_kwargs.get("language") == "es"
    assert model.last_kwargs.get("task") == "transcribe"
    assert model.last_kwargs.get("beam_size") == 5


@pytest.mark.asyncio
async def test_whisper_unsupported_language_raises_before_call(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    model = FakeWhisperModel()
    adapter = WhisperAdapter(model=model, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    with pytest.raises(UnsupportedLanguage):
        await adapter.transcribe(audio, lang="klingon")

    assert model.call_count == 0


@pytest.mark.asyncio
async def test_whisper_padding_unavailable_when_ffmpeg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATH cleared → ffmpeg cannot exec → PaddingUnavailable; model never called."""
    monkeypatch.setenv("PATH", "")

    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    model = FakeWhisperModel()
    adapter = WhisperAdapter(model=model, timeout_s=10.0)

    with pytest.raises(PaddingUnavailable, match=r"ffmpeg"):
        await adapter.transcribe(audio, lang="en")

    assert model.call_count == 0


@pytest.mark.asyncio
async def test_whisper_padding_failed_on_invalid_audio(tmp_path: Path) -> None:
    """Real ffmpeg + bad bytes → non-zero exit → PaddingFailed; model never called."""
    audio = tmp_path / "bad.wav"
    audio.write_bytes(b"not a wav file")

    model = FakeWhisperModel()
    adapter = WhisperAdapter(model=model, timeout_s=10.0)

    with pytest.raises(PaddingFailed, match=r"exit="):
        await adapter.transcribe(audio, lang="en")

    assert model.call_count == 0


class _HangingWhisperModel:
    """transcribe() blocks the asyncio.to_thread worker forever."""

    def __init__(self) -> None:
        self._block = threading.Event()
        self.call_count = 0

    def transcribe(
        self, audio_path: str, **kwargs: Any
    ) -> tuple[Iterator[FakeSegment], FakeInfo]:
        self.call_count += 1
        self._block.wait()
        # Unreachable in the timeout test; stays type-clean.
        return iter([]), FakeInfo()


@pytest.mark.asyncio
async def test_whisper_timeout_fires_at_60s(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    clock = FakeClock()
    model = _HangingWhisperModel()
    adapter = WhisperAdapter(model=model, clock=clock, timeout_s=60.0)
    _bypass_ffmpeg(adapter)

    task = asyncio.create_task(adapter.transcribe(audio, lang="en"))
    # Two-cycle warm-up: see test_ollama_adapter_timeout.py for the rationale.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await clock.tick(61.0)

    with pytest.raises(InferenceTimeout, match=r"exceeded 60\.0s"):
        await task

    model._block.set()  # release orphan worker thread


@pytest.mark.asyncio
async def test_whisper_inference_failure_raises_inference_failed(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    model = RaisingWhisperModel(error=RuntimeError("model crashed"))
    adapter = WhisperAdapter(model=model, timeout_s=10.0)
    _bypass_ffmpeg(adapter)

    with pytest.raises(InferenceFailed, match=r"Whisper inference failed"):
        await adapter.transcribe(audio, lang="en")

    assert model.call_count == 1


@pytest.mark.asyncio
async def test_whisper_emits_inference_complete_with_metrics(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])
    try:
        info = FakeInfo(language="es", language_probability=0.97, duration=4.5)
        model = FakeWhisperModel(segments=["hola mundo"], info=info)
        adapter = WhisperAdapter(model=model, timeout_s=10.0)
        _bypass_ffmpeg(adapter)

        await adapter.transcribe(audio, lang="es")
    finally:
        structlog.reset_defaults()

    events = [e for e in cap.entries if e["event"] == "inference_complete"]
    assert len(events) == 1
    e = events[0]
    assert e["detected_language"] == "es"
    assert e["language_probability"] == pytest.approx(0.97)
    assert e["duration_s"] == pytest.approx(4.5)
    assert e["segment_count"] == 1
    assert "latency_s" in e
    assert e["text_chars"] == len("hola mundo")
