"""Canonical Gemma 4 E2B adapter: ffmpeg padding, 25s Clock timeout, structlog.

Session 1A scope (Day 5): structural skeleton — exception hierarchy,
OllamaAdapter class shape, Clock-injected timeout race with think=False
hardcoded, ffmpeg preprocess() lifted from scripts/test_audio_smoke.py
with PaddingUnavailable / PaddingFailed branches, structlog event call
sites with minimal payloads, TranscriptionResult Pydantic validation
mapping ValidationError → InvalidToolCall.

Session 1B (this commit): structlog payload schema refinement,
_strip_json_fences helper for Gemma's markdown-wrapped JSON output,
padding-branch and InvalidToolCall tests.

Inherits two non-negotiable findings from Day 4 Session 4
(see scripts/gemma_hello.py docstring):

  1. think=False is hardcoded on every ollama.chat call. Without it,
     Gemma 4 E2B burns 1400-1800 tokens on internal deliberation before
     emitting content. ADR-003 records the decision.
  2. asyncio.to_thread cancellation is a Core-time guarantee only.
     The 25s timeout bounds Core return latency, not daemon computation.
     The worker thread wrapping ollama.chat continues running to natural
     completion; the daemon's HTTP response is generated and discarded
     client-side. InferenceTimeout's docstring carries this language.
"""

from __future__ import annotations

import asyncio
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

import ollama  # for ResponseError + RequestError, retried in transcribe()
import structlog
from pydantic import ValidationError

from core.clock import Clock
from core.language_matrix import (
    IMPLEMENTED_LANGS,
    LANGUAGE_NAMES,
    SupportedLang,
    is_implemented,
)
from core.rfl_schema import TranscriptionResult
from integration.system_clock import SYSTEM_CLOCK

log = structlog.get_logger(__name__)

MODEL = "gemma4:e2b"
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"
TRUNCATE_CHARS = 500
OPTIONS: dict[str, Any] = {
    "num_ctx": 8000,
    "temperature": 0.1,
    # num_predict=400 (not Phase 2.5's 1500) is the post-think=False budget.
    # The 1500 ceiling was masking Gemma 4 E2B's reasoning-mode behavior;
    # with think=False locked, English transcription completes in ~62 tokens.
    # See scripts/gemma_hello.py finding 2.
    "num_predict": 400,
}


def _build_prompt(lang: SupportedLang) -> str:
    """Build a language-aware transcription prompt.

    Single template with the language name interpolated. Per Day 7
    Session 1 Q3 lock: per-language prompt files deferred to Day 11+
    if empirical tuning warrants.
    """
    lang_name = LANGUAGE_NAMES[lang]
    return (
        f"You will receive an audio clip in {lang_name}. "
        f"Perform these two tasks in order and return as valid JSON "
        f"with keys 'transcription' and 'english_translation'. "
        f"Transcribe the audio in {lang_name}; provide an English "
        f"translation. Do not include any other text, explanation, "
        f"or commentary. Audio follows."
    )


class AdapterError(Exception):
    """Base for all OllamaAdapter failures."""


class PaddingUnavailable(AdapterError):
    """ffmpeg binary not on PATH. Demo cannot proceed without it."""


class PaddingFailed(AdapterError):
    """ffmpeg returned non-zero exit. stderr captured in the message."""


class InferenceTimeout(AdapterError):
    """25s timer won the race against ollama.chat.

    NOTE: this is a Core-time guarantee only. The worker thread wrapping
    ollama.chat continues running to natural completion; the daemon's
    HTTP request finishes in the background and the response is
    discarded client-side. See scripts/gemma_hello.py finding 1 and
    PROJECT_PLAN §7 Locked.
    """


class InvalidToolCall(AdapterError):
    """Gemma's response failed Pydantic validation. Raw response in message."""


class InferenceFailed(AdapterError):
    """Ollama inference failed after the retry-once mechanism gave up.

    Raised when both call attempts to ollama.chat surfaced
    ollama.ResponseError or ollama.RequestError. InferenceTimeout is
    a separate path and never converts to this class.
    """


class UnsupportedLanguage(AdapterError):
    """Lang parameter is not in IMPLEMENTED_LANGS.

    Distinct from PaddingFailed/InferenceTimeout/InferenceFailed —
    this fires BEFORE any preprocessing or inference attempt, when
    the caller asks for a lang we haven't wired up yet (e.g., 'ar'
    or 'fa' as of Day 7 Session 1). Fail loud rather than silently
    fall through to the English path.
    """


class OllamaAdapter:
    """Canonical Integration-layer adapter to Gemma 4 E2B via Ollama.

    The adapter is the single chokepoint between Core and the Ollama
    daemon. It owns: ffmpeg head-silence padding, the 25s timeout race
    against the daemon, think=False enforcement, and Pydantic
    validation of the model's response.

    Construction takes a Clock so the timeout branch can be exercised
    against FakeClock without spending wall-clock seconds.
    """

    def __init__(
        self,
        client: Any,
        clock: Clock = SYSTEM_CLOCK,
        timeout_s: float = 25.0,
        model: str = MODEL,
    ) -> None:
        self._client = client
        self._clock = clock
        self._timeout_s = timeout_s
        self._model = model

    async def transcribe(
        self, audio_path: Path, lang: str = "en"
    ) -> TranscriptionResult:
        """Pad audio, race ollama.chat against the clock, validate output.

        Raises UnsupportedLanguage if `lang` isn't yet wired
        (checked before any preprocessing, so no ffmpeg / inference
        side-effects fire); PaddingUnavailable / PaddingFailed if
        ffmpeg fails; InferenceTimeout if the 25s timer wins;
        InvalidToolCall if the response doesn't validate;
        InferenceFailed for other Ollama errors. Returns a validated
        TranscriptionResult on success.
        """
        if not is_implemented(lang):
            log.warning(
                "unsupported_language",
                audio_path=str(audio_path),
                model=self._model,
                lang=lang,
                implemented_langs=sorted(IMPLEMENTED_LANGS),
            )
            raise UnsupportedLanguage(
                f"lang={lang!r} is not yet implemented. "
                f"Currently supported: {sorted(IMPLEMENTED_LANGS)}"
            )

        base = {"audio_path": str(audio_path), "model": self._model, "lang": lang}
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
            audio_b64 = base64.b64encode(padded_path.read_bytes()).decode()
        finally:
            padded_path.unlink(missing_ok=True)

        prompt = _build_prompt(cast(SupportedLang, lang))
        messages = [{"role": "user", "content": prompt, "images": [audio_b64]}]
        start = self._clock.monotonic()
        try:
            response = await self._call_with_timeout(messages, base=base)
        except (ollama.ResponseError, ollama.RequestError) as first_err:
            log.warning(
                "ggml_retry_attempted",
                **base,
                error_class=type(first_err).__name__,
                error_msg_truncated=str(first_err)[:TRUNCATE_CHARS],
            )
            try:
                response = await self._call_with_timeout(messages, base=base)
            except (ollama.ResponseError, ollama.RequestError) as retry_err:
                log.error(
                    "inference_failed_after_retry",
                    **base,
                    error_class=type(retry_err).__name__,
                    error_msg_truncated=str(retry_err)[:TRUNCATE_CHARS],
                )
                raise InferenceFailed(
                    f"Ollama inference failed after retry: {retry_err}"
                ) from retry_err
        latency_s = self._clock.monotonic() - start

        content = self._extract_content(response)
        stripped = self._strip_json_fences(content)
        try:
            result = TranscriptionResult.model_validate_json(stripped)
        except ValidationError as e:
            log.warning(
                "validation_failed",
                **base,
                raw_content_truncated=content[:TRUNCATE_CHARS],
                validation_error_class=type(e).__name__,
            )
            raise InvalidToolCall(f"Gemma response failed validation: {e}") from e

        load_duration_ns = getattr(response, "load_duration", None)
        load_duration_s = (
            load_duration_ns / 1_000_000_000 if load_duration_ns is not None else None
        )
        log.info(
            "inference_complete",
            **base,
            latency_s=latency_s,
            eval_count=getattr(response, "eval_count", None),
            done_reason=getattr(response, "done_reason", None),
            prompt_eval_count=getattr(response, "prompt_eval_count", None),
            load_duration_s=load_duration_s,
        )
        return result

    async def _call_with_timeout(
        self, messages: list[dict[str, Any]], *, base: dict[str, str]
    ) -> Any:
        """Race ollama.chat against self._clock.sleep(timeout_s).

        think=False is hardcoded here, NOT a constructor argument. ADR-003
        records the lock; do not parameterize.
        """
        start = self._clock.monotonic()
        call = asyncio.create_task(
            asyncio.to_thread(
                self._client.chat,
                model=self._model,
                messages=messages,
                options=OPTIONS,
                think=False,
            )
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
            # Propagate raw exceptions (ollama.ResponseError /
            # ollama.RequestError, or any other) to transcribe(), which
            # owns the retry policy and InferenceFailed conversion.
            return call.result()

        elapsed = self._clock.monotonic() - start
        log.warning(
            "inference_timeout",
            **base,
            elapsed_s=elapsed,
            timeout_s=self._timeout_s,
        )
        raise InferenceTimeout(
            f"Gemma inference exceeded {self._timeout_s}s "
            f"(elapsed={elapsed:.2f}s). Worker thread continues running "
            f"to natural completion (Core-time guarantee only)."
        )

    @staticmethod
    def _extract_content(response: Any) -> str:
        """Pull message.content off both object-shaped and dict-shaped responses."""
        if hasattr(response, "message"):
            return str(response.message.content)
        return str(response.get("message", {}).get("content", ""))

    @staticmethod
    def _strip_json_fences(content: str) -> str:
        """Strip markdown code fences from Gemma's JSON output if present.

        Gemma 4 E2B sometimes wraps its JSON in ```json ... ``` or bare
        ``` ... ``` despite the prompt. Pattern lifted from
        scripts/test_audio_smoke.py:57-65 and tightened for strict
        pre-validation use.
        """
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]
        if content.endswith("```"):
            content = content[:-3].rstrip()
        return content

    def _preprocess(
        self, src: Path, dst: Path, *, base: dict[str, str] | None = None
    ) -> None:
        """Pad head silence and resample to 16kHz mono WAV.

        Lifted from scripts/test_audio_smoke.py:32-43; the only change
        is replacing subprocess.run(check=True) with explicit
        FileNotFoundError / non-zero-exit handling so we raise the named
        adapter exceptions instead of CalledProcessError, and emit
        structlog warnings before each raise.
        """
        base = base or {"audio_path": str(src), "model": self._model}
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
