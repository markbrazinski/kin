"""Two-stage orchestrator: Whisper ASR → Gemma translation → TranscriptionResult.

Lives in Integration because both stages are I/O. The pipeline is
stateless; adapters are constructor-injected so probes and the demo
share the same configuration without re-instantiating the underlying
WhisperModel (47s load) or Ollama client per call.

English short-circuits the Gemma translate call: Whisper already
produced English text, and routing it through Gemma adds latency and a
non-zero risk of fabricated commentary for no quality gain.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog

from core.rfl_schema import TranscriptionResult

log = structlog.get_logger(__name__)


class _Transcriber(Protocol):
    async def transcribe(self, audio_path: Path, lang: str) -> str: ...


class _Translator(Protocol):
    async def translate(self, text: str, source_lang: str) -> str: ...


@dataclass
class PipelineMetrics:
    whisper_latency_s: float
    gemma_latency_s: float
    total_latency_s: float
    skipped_translation: bool


async def transcribe_and_translate(
    audio_path: Path,
    lang: str,
    *,
    whisper: _Transcriber,
    ollama: _Translator,
) -> TranscriptionResult:
    """Demo-facing convenience wrapper. Drops the metrics tuple."""
    result, _metrics = await transcribe_and_translate_with_metrics(
        audio_path, lang, whisper=whisper, ollama=ollama
    )
    return result


async def transcribe_and_translate_with_metrics(
    audio_path: Path,
    lang: str,
    *,
    whisper: _Transcriber,
    ollama: _Translator,
) -> tuple[TranscriptionResult, PipelineMetrics]:
    """Run Whisper then Gemma; assemble TranscriptionResult; report stage timings.

    Adapter exceptions propagate unchanged. The pipeline does not
    convert PaddingFailed, InferenceTimeout, etc. — callers handle the
    shared adapter error vocabulary directly.
    """
    log.info("pipeline_start", audio_path=str(audio_path), lang=lang)

    t0 = time.perf_counter()
    source_text = await whisper.transcribe(audio_path, lang)
    t1 = time.perf_counter()
    whisper_latency_s = t1 - t0

    if lang == "en":
        english = source_text
        gemma_latency_s = 0.0
        skipped = True
    else:
        english = await ollama.translate(source_text, lang)
        gemma_latency_s = time.perf_counter() - t1
        skipped = False

    total_latency_s = time.perf_counter() - t0
    metrics = PipelineMetrics(
        whisper_latency_s=whisper_latency_s,
        gemma_latency_s=gemma_latency_s,
        total_latency_s=total_latency_s,
        skipped_translation=skipped,
    )

    log.info(
        "pipeline_complete",
        audio_path=str(audio_path),
        lang=lang,
        whisper_latency_s=whisper_latency_s,
        gemma_latency_s=gemma_latency_s,
        total_latency_s=total_latency_s,
        skipped_translation=skipped,
    )

    result = TranscriptionResult(
        transcription=source_text, english_translation=english
    )
    return result, metrics
