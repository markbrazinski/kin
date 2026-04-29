"""Tests for the escalate_crisis tool schema + Pydantic round-trip (S6).

The Pydantic model is what the pipeline validates against; the JSON
Schema is what Gemma sees. Both must agree on the required fields and
their types so a successful tool_call returns args that Pydantic
accepts. Validation failures must raise cleanly so
_format_crisis_referral can fall back to the static lookup.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from integration.escalate_crisis_tool import (
    ESCALATE_CRISIS_TOOL,
    EscalateCrisisArgs,
)

# ─── 1. Schema + Pydantic round-trip ──────────────────────────────


def test_escalate_crisis_tool_schema_valid_args_round_trip() -> None:
    """One test covers (a) valid args round-trip, (b) Schema/Pydantic
    required-field agreement, (c) missing-field validation.

    Why one test: the contract is "Pydantic and JSON Schema agree" —
    splitting into three would weaken the assertion that they agree
    AS A UNIT. Floor 8 lock; this is test 1 of 8.
    """
    # (a) Valid args round-trip.
    args = EscalateCrisisArgs(
        referral_organization="Cruz Roja",
        locale_aware_message="Por favor llame a Cruz Roja al 911 ahora.",
    )
    assert args.referral_organization == "Cruz Roja"
    assert args.locale_aware_message.startswith("Por favor")

    # (b) Schema/Pydantic required-field agreement. If either drifts,
    # a successful tool_call could produce args the model rejects.
    schema_required = set(
        ESCALATE_CRISIS_TOOL["function"]["parameters"]["required"]
    )
    assert schema_required == {"referral_organization", "locale_aware_message"}
    assert ESCALATE_CRISIS_TOOL["function"]["name"] == "escalate_crisis"

    # (c) Missing-field validation — _format_crisis_referral catches
    # this exception class and falls back to the static lookup.
    with pytest.raises(ValidationError):
        EscalateCrisisArgs(  # type: ignore[call-arg]
            locale_aware_message="message without an organization"
        )
    with pytest.raises(ValidationError):
        EscalateCrisisArgs(  # type: ignore[call-arg]
            referral_organization="organization without a message"
        )
