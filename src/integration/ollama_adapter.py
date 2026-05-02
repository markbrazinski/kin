"""Canonical Gemma 4 E2B text-only adapter: 25s Clock timeout, structlog.

Day 10 refactor: audio path replaced by Whisper (see whisper_adapter.py +
results/whisper_baseline_20260426_114250.md). OllamaAdapter is now a
text-in/text-out interface to Gemma 4 E2B for translation (and, in
later phases, RFL reasoning + native tool calls).

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
from typing import Any, cast

import ollama  # for ResponseError + RequestError, retried in translate()
import structlog

from core.clock import Clock
from core.language_matrix import (
    IMPLEMENTED_LANGS,
    LANGUAGE_NAMES,
    SupportedLang,
    is_implemented,
)
from core.tool_calling import ToolCallResult
from integration._errors import (
    AdapterError,
    InferenceFailed,
    InferenceTimeout,
    InvalidToolCall,
)
from integration.system_clock import SYSTEM_CLOCK

__all__ = [
    "AdapterError",
    "InferenceFailed",
    "InferenceTimeout",
    "InvalidToolCall",
    "MODEL",
    "OPTIONS",
    "OllamaAdapter",
    "UnsupportedLanguage",
]

log = structlog.get_logger(__name__)

MODEL = "gemma4:e2b"
TRUNCATE_CHARS = 500
OPTIONS: dict[str, Any] = {
    "num_ctx": 8000,
    "temperature": 0.1,
    "num_predict": 400,
}


def _build_translate_prompt(text: str, source_lang: SupportedLang) -> str:
    """Build a plain-text translation prompt.

    Plain text first per ADR (Day 10 plan §8d): if probe shows wrapped
    or commentary-laden output, follow up with `format="json"` and a
    minimal {"english": str} schema in a separate change.
    """
    lang_name = LANGUAGE_NAMES[source_lang]
    return (
        f"Translate the following {lang_name} text to English. "
        f"Return only the English translation as plain text, with no "
        f"commentary, no quotation marks, and no explanation.\n\n"
        f"{lang_name} text: {text}"
    )


class UnsupportedLanguage(AdapterError):
    """Lang parameter is not in IMPLEMENTED_LANGS.

    Distinct from InferenceTimeout / InferenceFailed — this fires
    BEFORE any inference attempt, when the caller asks for a lang we
    haven't wired up yet. Fail loud rather than silently falling
    through to a default path.
    """


class OllamaAdapter:
    """Integration-layer text-in/text-out adapter to Gemma 4 E2B via Ollama.

    The adapter owns: the 25s timeout race against the daemon,
    think=False enforcement, retry-once on transient ollama.ResponseError
    or ollama.RequestError, and translation of model exceptions into the
    shared adapter error vocabulary.

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

    async def translate(self, text: str, source_lang: str) -> str:
        """Race ollama.chat against the clock; return the English translation.

        Raises UnsupportedLanguage if `source_lang` isn't implemented;
        InferenceTimeout if the 25s timer wins; InferenceFailed if both
        ollama.chat attempts surface ollama.ResponseError or
        ollama.RequestError. Returns the stripped English translation
        on success.
        """
        if not is_implemented(source_lang):
            log.warning(
                "unsupported_language",
                model=self._model,
                source_lang=source_lang,
                implemented_langs=sorted(IMPLEMENTED_LANGS),
            )
            raise UnsupportedLanguage(
                f"source_lang={source_lang!r} is not yet implemented. "
                f"Currently supported: {sorted(IMPLEMENTED_LANGS)}"
            )

        base = {
            "model": self._model,
            "source_lang": source_lang,
            "text_chars": str(len(text)),
        }
        log.info("adapter_call_start", **base, timeout_s=self._timeout_s)

        prompt = _build_translate_prompt(text, cast(SupportedLang, source_lang))
        messages = [{"role": "user", "content": prompt}]
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

        content = self._extract_content(response).strip()

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
            output_chars=len(content),
        )
        return content

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult:
        """Race ollama.chat (with tools=) against the clock; return a ToolCallResult.

        Mirrors translate() shape: Clock-injected 25s timeout race,
        retry-once on transient ollama.ResponseError / RequestError,
        think=False (ADR-003). Returns the raw arguments dict —
        caller validates against any tool-specific Pydantic model.

        Raises:
          InvalidToolCall — model emitted no tool_calls; or returned
            tool name not in `tools`; or tool_call structure malformed
            (missing function/name/arguments) or arguments not a dict.
          InferenceTimeout — 25s clock fired before the daemon returned.
          InferenceFailed — both attempts surfaced ollama.ResponseError
            or ollama.RequestError.
        """
        base = {
            "model": self._model,
            "tool_count": str(len(tools)),
            "message_count": str(len(messages)),
        }
        log.info("tool_call_invoked", **base, timeout_s=self._timeout_s)

        start = self._clock.monotonic()
        try:
            response = await self._call_with_timeout(
                messages, base=base, tools=tools
            )
        except (ollama.ResponseError, ollama.RequestError) as first_err:
            log.warning(
                "ggml_retry_attempted",
                **base,
                error_class=type(first_err).__name__,
                error_msg_truncated=str(first_err)[:TRUNCATE_CHARS],
            )
            try:
                response = await self._call_with_timeout(
                    messages, base=base, tools=tools
                )
            except (ollama.ResponseError, ollama.RequestError) as retry_err:
                log.error(
                    "inference_failed_after_retry",
                    **base,
                    error_class=type(retry_err).__name__,
                    error_msg_truncated=str(retry_err)[:TRUNCATE_CHARS],
                )
                raise InferenceFailed(
                    f"Ollama tool_call failed after retry: {retry_err}"
                ) from retry_err
        latency_s = self._clock.monotonic() - start

        result = self._parse_tool_call(response, tools=tools, base=base)

        log.info(
            "tool_call_returned",
            **base,
            latency_s=latency_s,
            tool_name=result.name,
            tool_args=result.arguments,
            eval_count=getattr(response, "eval_count", None),
            done_reason=getattr(response, "done_reason", None),
            prompt_eval_count=getattr(response, "prompt_eval_count", None),
        )
        return result

    def _parse_tool_call(
        self,
        response: Any,
        *,
        tools: list[dict[str, Any]],
        base: dict[str, str],
    ) -> ToolCallResult:
        """Pull a single ToolCallResult off a raw SDK response.

        Wire format (Apr 28 hello-world + Apr 29 multilang sweep):
        response.message.tool_calls is list | None. Each item exposes
        .function.name (str) and .function.arguments (already-parsed
        dict, NOT a JSON string).
        """
        # Normalize message access for both object-shaped and dict-shaped
        # responses (mirrors _extract_content).
        if hasattr(response, "message"):
            message = response.message
            tool_calls = getattr(message, "tool_calls", None)
        else:
            message = response.get("message", {})
            tool_calls = (
                message.get("tool_calls") if isinstance(message, dict) else None
            )

        if not tool_calls:
            log.warning("tool_call_no_tools_emitted", **base)
            raise InvalidToolCall("Model emitted no tool calls")

        tc = tool_calls[0]

        # Pull function/name/arguments off either object or dict shapes.
        if isinstance(tc, dict):
            fn = tc.get("function")
        else:
            fn = getattr(tc, "function", None)
        if fn is None:
            raise InvalidToolCall("Malformed tool_call: missing function field")

        if isinstance(fn, dict):
            name = fn.get("name")
            arguments = fn.get("arguments")
        else:
            name = getattr(fn, "name", None)
            arguments = getattr(fn, "arguments", None)

        if not isinstance(name, str):
            raise InvalidToolCall(
                f"Malformed tool_call: name is not a string ({type(name).__name__})"
            )

        allowed = {t["function"]["name"] for t in tools}
        if name not in allowed:
            raise InvalidToolCall(
                f"Tool name {name!r} not in allowed set {sorted(allowed)}"
            )

        if not isinstance(arguments, dict):
            raise InvalidToolCall(
                f"Tool arguments not a dict ({type(arguments).__name__})"
            )

        return ToolCallResult(name=name, arguments=arguments)

    async def _call_with_timeout(
        self,
        messages: list[dict[str, Any]],
        *,
        base: dict[str, str],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Race ollama.chat against self._clock.sleep(timeout_s).

        think=False is hardcoded here, NOT a constructor argument. ADR-003
        records the lock; do not parameterize. Optional `tools` is
        passed through to the SDK only when non-None — translate path
        omits it entirely so the wire payload is byte-identical to
        pre-S3 behavior.
        """
        start = self._clock.monotonic()
        chat_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "options": OPTIONS,
            "think": False,
        }
        if tools is not None:
            chat_kwargs["tools"] = tools
        call = asyncio.create_task(
            asyncio.to_thread(self._client.chat, **chat_kwargs)
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
            # ollama.RequestError, or any other) to translate(), which
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

        Reserved for future structured-output paths (tool calls,
        schema-validated multi-turn). The Day 10 translate path returns
        plain text and does not use this helper. Pattern lifted from
        scripts/test_audio_smoke.py:57-65.
        """
        content = content.strip()
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]
        if content.endswith("```"):
            content = content[:-3].rstrip()
        return content
