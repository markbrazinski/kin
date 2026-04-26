"""Canonical faster-whisper adapter: ffmpeg padding, Clock-injected timeout, structlog.

Owns offline ASR for the four KIN languages (en/es/ar/fa). Mirrors
OllamaAdapter's structural patterns — Clock-injected timeout race,
structlog event payloads, ffmpeg head-silence preprocessing — but the
output is plain source-language text, not a TranscriptionResult.
Translation and TranscriptionResult assembly live in
`integration.transcription_pipeline`.

Day 10 baseline (results/whisper_baseline_20260426_114250.md) confirmed
faster-whisper medium (int8 CPU) recovers full utterances on 5/5
fixtures including the laptop-mic English clip that broke Gemma.
Mean inference ~7.7s; 60s adapter timeout has comfortable headroom.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

import structlog

from core.clock import Clock
from core.language_matrix import (
    IMPLEMENTED_LANGS,
    SupportedLang,
    is_implemented,
)
from integration._errors import AdapterError, InferenceFailed, InferenceTimeout
from integration.system_clock import SYSTEM_CLOCK

log = structlog.get_logger(__name__)

WHISPER_MODEL_SIZE = "medium"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_BEAM_SIZE = 5
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"
TRUNCATE_CHARS = 500


class PaddingUnavailable(AdapterError):
    """ffmpeg binary not on PATH. Demo cannot proceed without it."""


class PaddingFailed(AdapterError):
    """ffmpeg returned non-zero exit. stderr captured in the message."""


class UnsupportedLanguage(AdapterError):
    """Lang parameter is not in IMPLEMENTED_LANGS."""


class WhisperAdapter:
    """Integration-layer adapter to faster-whisper.

    The adapter is the single chokepoint for audio→text. It owns:
    ffmpeg head-silence padding, the Clock-injected timeout race,
    and translation of model exceptions into the shared adapter
    error vocabulary.

    `model` is constructor-injected so tests pass a fake; production
    callers instantiate `WhisperModel("medium", device="cpu",
    compute_type="int8")` once at process startup.
    """

    def __init__(
        self,
        model: Any,
        clock: Clock = SYSTEM_CLOCK,
        timeout_s: float = 60.0,
        beam_size: int = WHISPER_BEAM_SIZE,
        model_label: str = f"faster-whisper:{WHISPER_MODEL_SIZE}",
    ) -> None:
        self._model = model
        self._clock = clock
        self._timeout_s = timeout_s
        self._beam_size = beam_size
        self._model_label = model_label

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        """Pad audio, race model.transcribe against the clock, return source text.

        Raises UnsupportedLanguage if `lang` isn't yet wired (checked
        before any preprocessing); PaddingUnavailable / PaddingFailed
        if ffmpeg fails; InferenceTimeout if the timer wins;
        InferenceFailed if WhisperModel raises a non-timeout exception.
        Returns the concatenated, stripped source-language text on
        success.
        """
        if not is_implemented(lang):
            log.warning(
                "unsupported_language",
                audio_path=str(audio_path),
                model=self._model_label,
                lang=lang,
                implemented_langs=sorted(IMPLEMENTED_LANGS),
            )
            raise UnsupportedLanguage(
                f"lang={lang!r} is not yet implemented. "
                f"Currently supported: {sorted(IMPLEMENTED_LANGS)}"
            )

        base = {
            "audio_path": str(audio_path),
            "model": self._model_label,
            "lang": lang,
        }
        log.info("adapter_call_start", **base, timeout_s=self._timeout_s)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            padded_path = Path(tmp.name)
        try:
            src_bytes = audio_path.stat().st_size
            self._preprocess(audio_path, padded_path, base=base)
            log.info(
                "padding_applied",
                **base,
                src_bytes=src_bytes,
                dst_bytes=padded_path.stat().st_size,
                pad_filter=PAD_FILTER,
            )
            text, info = await self._call_with_timeout(
                padded_path, cast(SupportedLang, lang), base=base
            )
        finally:
            padded_path.unlink(missing_ok=True)

        log.info(
            "inference_complete",
            **base,
            latency_s=info["latency_s"],
            detected_language=info["detected_language"],
            language_probability=info["language_probability"],
            duration_s=info["duration_s"],
            segment_count=info["segment_count"],
            text_chars=len(text),
        )
        return text

    async def _call_with_timeout(
        self,
        padded_path: Path,
        lang: SupportedLang,
        *,
        base: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        """Race WhisperModel.transcribe against self._clock.sleep(timeout_s).

        Segment iteration must run inside the worker thread — faster-whisper's
        segment generator triggers actual decode on iteration, not at
        transcribe() return.
        """
        start = self._clock.monotonic()
        call = asyncio.create_task(
            asyncio.to_thread(self._run_blocking, padded_path, lang)
        )
        timer = asyncio.create_task(self._clock.sleep(self._timeout_s))
        done, pending = await asyncio.wait(
            {call, timer}, return_when=asyncio.FIRST_COMPLETED
        )
        for p in pending:
            p.cancel()
        if call in done:
            for p in pending:
                try:
                    await p
                except asyncio.CancelledError:
                    pass
            try:
                return call.result()
            except Exception as exc:
                log.error(
                    "inference_failed",
                    **base,
                    error_class=type(exc).__name__,
                    error_msg_truncated=str(exc)[:TRUNCATE_CHARS],
                )
                raise InferenceFailed(
                    f"Whisper inference failed: {exc}"
                ) from exc

        elapsed = self._clock.monotonic() - start
        log.warning(
            "inference_timeout",
            **base,
            elapsed_s=elapsed,
            timeout_s=self._timeout_s,
        )
        raise InferenceTimeout(
            f"Whisper inference exceeded {self._timeout_s}s "
            f"(elapsed={elapsed:.2f}s). Worker thread continues running "
            f"to natural completion (Core-time guarantee only)."
        )

    def _run_blocking(
        self, padded_path: Path, lang: SupportedLang
    ) -> tuple[str, dict[str, Any]]:
        """Sync body of the timeout race. Exercised inside asyncio.to_thread."""
        wall_start = self._clock.monotonic()
        segments, info = self._model.transcribe(
            str(padded_path),
            task="transcribe",
            language=lang,
            beam_size=self._beam_size,
        )
        text_parts: list[str] = []
        seg_count = 0
        for seg in segments:
            text_parts.append(seg.text)
            seg_count += 1
        text = "".join(text_parts).strip()
        elapsed = self._clock.monotonic() - wall_start
        return text, {
            "latency_s": elapsed,
            "detected_language": info.language,
            "language_probability": float(info.language_probability),
            "duration_s": float(info.duration),
            "segment_count": seg_count,
        }

    def _preprocess(
        self, src: Path, dst: Path, *, base: dict[str, str] | None = None
    ) -> None:
        """Pad head silence and resample to 16kHz mono WAV.

        Lifted verbatim from ollama_adapter._preprocess (Day 5 origin in
        scripts/test_audio_smoke.py:32-43). Whisper consumes 16kHz mono
        s16 cleanly; the head-silence pad protects against the same
        first-second drop pattern observed under Gemma.
        """
        base = base or {"audio_path": str(src), "model": self._model_label}
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(src),
                    "-af",
                    PAD_FILTER,
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-sample_fmt",
                    "s16",
                    str(dst),
                ],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            log.warning(
                "padding_unavailable",
                **base,
                error_class=type(e).__name__,
                error_msg=str(e),
            )
            raise PaddingUnavailable("ffmpeg not on PATH") from e
        if result.returncode != 0:
            log.warning(
                "padding_failed",
                **base,
                returncode=result.returncode,
                stderr_truncated=result.stderr[:TRUNCATE_CHARS],
            )
            raise PaddingFailed(
                f"ffmpeg exit={result.returncode}: {result.stderr.strip()}"
            )
