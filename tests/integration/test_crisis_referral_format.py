"""Tests for _format_crisis_referral — the S6 helper that wraps Gemma
escalate_crisis with a static-lookup fallback.

Helper-level tests; pipeline-level tests live in test_ingest_audio.py.
The helper's contract:
  - On success, returns (referral_organization, locale_aware_message)
    from the validated EscalateCrisisArgs.
  - On any tool_call or validation failure, returns
    (_REFERRAL_ORG_BY_LANG[lang], "") so the safety path always
    completes.
  - Emits crisis_referral_formatted on success and
    crisis_referral_fallback on failure (for SSE-bridged sidebar).
"""
from __future__ import annotations

from typing import Any

import pytest
import structlog

from core import safety_rules
from core.tool_calling import ToolCallResult
from integration._errors import InferenceTimeout
from integration.transcription_pipeline import (
    _REFERRAL_ORG_BY_LANG,
    _format_crisis_referral,
)


class _ToolCallStub:
    """Minimal stub for the _OllamaPort.tool_call surface.

    response_or_exc: a ToolCallResult to return, OR an Exception class
    instance to raise. Constructed once per test so the helper sees
    exactly one tool_call invocation.
    """

    def __init__(self, response_or_exc: ToolCallResult | Exception) -> None:
        self._payload = response_or_exc
        self.calls: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    async def translate(self, text: str, source_lang: str) -> str:
        # Not exercised by _format_crisis_referral, but the
        # _OllamaPort Protocol requires it; raise so an accidental
        # invocation surfaces.
        raise AssertionError(
            "_format_crisis_referral must not invoke translate"
        )

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult:
        self.calls.append((messages, tools))
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _safety_for(lang: str = "es") -> safety_rules.SafetyResult:
    """Build a SafetyResult that matches what classify() returns on a
    real crisis match. matched_keywords is a sorted list with at least
    one entry so the helper's payload includes a keyword summary.
    """
    return safety_rules.SafetyResult(
        is_crisis=True,
        matched_keywords=["me suicido"],
        suggested_action="block_intake",
        crisis_resources_locale=lang,
    )


# ─── 2. Happy path: helper invokes Gemma + returns args ───────────


@pytest.mark.asyncio
async def test_format_crisis_referral_invokes_gemma_tool_call() -> None:
    safety = _safety_for("es")
    stub = _ToolCallStub(
        ToolCallResult(
            name="escalate_crisis",
            arguments={
                "referral_organization": "Cruz Roja",
                "locale_aware_message": "Por favor llame a Cruz Roja.",
            },
        )
    )

    org, message = await _format_crisis_referral(
        transcription="me suicido ahora",
        lang="es",
        safety=safety,
        ollama=stub,
    )

    assert org == "Cruz Roja"
    assert message == "Por favor llame a Cruz Roja."

    # Tool was invoked exactly once with the escalate_crisis schema.
    assert len(stub.calls) == 1
    _msgs, tools = stub.calls[0]
    tool_names = {t["function"]["name"] for t in tools}
    assert tool_names == {"escalate_crisis"}


# ─── 3. Tool-call failure paths fall back to static lookup ────────


@pytest.mark.asyncio
async def test_format_crisis_referral_falls_back_on_tool_call_failure() -> None:
    """One representative exception class (InferenceTimeout) to lock the
    contract. The except clause in _format_crisis_referral catches all
    three of {InferenceTimeout, InferenceFailed, InvalidToolCall} via a
    single tuple — same handler for all three; one test exercises the
    handler. Adding two more parametrize cases would just re-test the
    Python except-tuple semantics.
    """
    safety = _safety_for("es")
    stub = _ToolCallStub(InferenceTimeout("simulated timeout"))

    org, message = await _format_crisis_referral(
        transcription="me suicido ahora",
        lang="es",
        safety=safety,
        ollama=stub,
    )

    assert org == _REFERRAL_ORG_BY_LANG["es"]
    assert message == ""


# ─── 4. Validation-error fallback ─────────────────────────────────


@pytest.mark.asyncio
async def test_format_crisis_referral_falls_back_on_validation_error() -> None:
    """Gemma returns args dict missing locale_aware_message; helper
    catches ValidationError and falls back rather than letting it
    crash the safety path.
    """
    safety = _safety_for("ar")
    stub = _ToolCallStub(
        ToolCallResult(
            name="escalate_crisis",
            arguments={"referral_organization": "الصليب الأحمر"},
        )
    )

    org, message = await _format_crisis_referral(
        transcription="اقتلني",
        lang="ar",
        safety=safety,
        ollama=stub,
    )

    assert org == _REFERRAL_ORG_BY_LANG["ar"]
    assert message == ""


# ─── 8. Structlog event names land for SSE bridge ─────────────────


@pytest.mark.asyncio
async def test_format_crisis_referral_emits_structlog_events() -> None:
    """Locks the structlog event names that the frontend StructlogSidebar
    auto-categorizes amber via the crisis_* prefix. If these names
    drift, the sidebar still renders them but loses the amber band.
    """
    safety = _safety_for("es")

    # Success path: crisis_referral_formatted.
    success_stub = _ToolCallStub(
        ToolCallResult(
            name="escalate_crisis",
            arguments={
                "referral_organization": "Cruz Roja",
                "locale_aware_message": "Por favor llame a Cruz Roja.",
            },
        )
    )
    with structlog.testing.capture_logs() as cap_logs:
        await _format_crisis_referral(
            transcription="me suicido ahora",
            lang="es",
            safety=safety,
            ollama=success_stub,
        )
    success_events = [log["event"] for log in cap_logs]
    assert "crisis_referral_formatted" in success_events
    assert "crisis_referral_fallback" not in success_events

    # Failure path: crisis_referral_fallback.
    fail_stub = _ToolCallStub(InferenceTimeout("simulated"))
    with structlog.testing.capture_logs() as cap_logs:
        await _format_crisis_referral(
            transcription="me suicido ahora",
            lang="es",
            safety=safety,
            ollama=fail_stub,
        )
    fail_events = [log["event"] for log in cap_logs]
    assert "crisis_referral_fallback" in fail_events
    assert "crisis_referral_formatted" not in fail_events
