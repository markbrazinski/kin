"""Crisis-phrase detection — first-pass keyword classifier.

Pure-logic Core module. No I/O. Runs BEFORE the adapter so a person
in distress is routed to crisis resources rather than processed as
intake. Multilingual keyword expansion (ES/AR/FA) and semantic
detection via Gemma are Day 7-9; this session lands the EN keyword
path only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SafetyResult(BaseModel):
    """Result of safety classification.

    Schema differs from test_strategy §2's representative example
    (escalate/match_path/allow_rfl_tools); concrete shape adopted
    here for v1, may converge as semantic detection lands Day 7-9.
    """

    is_crisis: bool
    matched_keywords: list[str]
    suggested_action: Literal["block_intake", "proceed"]
    crisis_resources_locale: str | None


_EN_CRISIS_KEYWORDS: tuple[str, ...] = (
    # Self-harm
    "kill myself",
    "end my life",
    "suicide",
    "want to die",
    "hurt myself",
    # Imminent harm to others
    "going to hurt",
    "going to kill",
    "going to attack",
    # Immediate-danger context (note: "emergency" intentionally
    # excluded — over-triggers on legitimate intake speech like
    # "I left during the emergency")
    "immediate danger",
)


def classify(text: str, lang: str = "en") -> SafetyResult:
    if lang == "en":
        return _classify_english(text)
    # TODO Day 7-9: Spanish, Arabic, Farsi keyword sets + semantic
    # detection via Gemma. Intentionally permissive default — safer
    # to log "not yet implemented for lang=X, proceeding" than to
    # false-positive block intake on a Spanish speaker because the
    # keyword list is incomplete.
    return SafetyResult(
        is_crisis=False,
        matched_keywords=[],
        suggested_action="proceed",
        crisis_resources_locale=None,
    )


def _classify_english(text: str) -> SafetyResult:
    # Cap analyzed text at 5000 chars; intake utterances are typically
    # <500 chars. If they're longer, we likely have corrupt input or
    # a misuse — better to scan a prefix than blow memory on
    # adversarial input.
    haystack = text[:5000].lower()
    matched = [kw for kw in _EN_CRISIS_KEYWORDS if kw in haystack]
    if matched:
        return SafetyResult(
            is_crisis=True,
            matched_keywords=matched,
            suggested_action="block_intake",
            crisis_resources_locale="en",
        )
    return SafetyResult(
        is_crisis=False,
        matched_keywords=[],
        suggested_action="proceed",
        crisis_resources_locale=None,
    )
