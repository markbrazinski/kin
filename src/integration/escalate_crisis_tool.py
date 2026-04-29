"""Module-level constants for the escalate_crisis tool.

ESCALATE_CRISIS_TOOL is the JSON Schema dict passed to
OllamaAdapter.tool_call() on the crisis branch (S6). Mirrors the
shape of EXTRACT_INTAKE_FIELDS_TOOL so the adapter's existing
generic tool_call(messages, tools) contract handles both.

EscalateCrisisArgs is the Pydantic model the pipeline uses to
validate the arguments dict returned by tool_call(). The
deterministic safety_rules.classify is the sole safety gate; this
tool's role is locale-aware FORMATTING of an already-classified
crisis. See ADR-004 REV 2.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

ESCALATE_CRISIS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "escalate_crisis",
        "description": (
            "Format a locale-aware crisis referral for a person in "
            "immediate distress. The user's safety has already been "
            "classified by a deterministic keyword classifier; do not "
            "re-evaluate whether this is a crisis. Your job is to "
            "choose an appropriate humanitarian referral organization "
            "name in the speaker's language and write a brief, calm "
            "referral message in that language directing them to "
            "immediate help."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "referral_organization": {
                    "type": "string",
                    "description": (
                        "Name of an appropriate humanitarian referral "
                        "organization, written in the speaker's language "
                        "(e.g., 'Cruz Roja', 'الصليب الأحمر', "
                        "'صلیب سرخ', 'ICRC Family Links Network'). "
                        "Prefer well-known regional NGOs and Red Cross / "
                        "Red Crescent Movement organizations."
                    ),
                },
                "locale_aware_message": {
                    "type": "string",
                    "description": (
                        "A brief, calm referral message in the speaker's "
                        "language directing them to immediate help. Two "
                        "to three sentences. Do not assert facts about "
                        "the person's situation; do not promise outcomes."
                    ),
                },
            },
            "required": ["referral_organization", "locale_aware_message"],
        },
    },
}


class EscalateCrisisArgs(BaseModel):
    """Validates raw arguments dict from escalate_crisis tool calls.

    Used by S6 ingest_audio() crisis branch to validate
    ToolCallResult.arguments before passing referral_organization
    to _persist_crisis_record. On any validation failure the crisis
    branch falls back to the static _REFERRAL_ORG_BY_LANG lookup —
    failure here cannot break the safety path.

    extra='ignore' so future tool-schema additions don't break
    consumers that still validate against the older shape.
    """

    model_config = ConfigDict(extra="ignore")

    referral_organization: str
    locale_aware_message: str
