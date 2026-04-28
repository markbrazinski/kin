"""Crisis-phrase detection — keyword classifier across the supported language set.

Pure-logic Core module. No I/O. Runs BEFORE the adapter so a person
in distress is routed to crisis resources rather than processed as
intake. Day 10 Session 2 expanded coverage from EN to all four locked
KIN languages (en/es/ar/fa). Day 10 Session 5 adds fr/uk as
validated-and-claimed coverage for the Devpost Digital Equity &
Inclusivity prize. Semantic detection via Gemma remains a Day 11+
scope item.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from core.language_matrix import IMPLEMENTED_LANGS, SupportedLang


class SafetyResult(BaseModel):
    """Result of safety classification.

    Schema differs from test_strategy §2's representative example
    (escalate/match_path/allow_rfl_tools); concrete shape adopted
    here for v1, may converge as semantic detection lands Day 11+.
    """

    is_crisis: bool
    matched_keywords: list[str]
    suggested_action: Literal["block_intake", "proceed"]
    crisis_resources_locale: str | None


# Keyword sources:
# - EN: Day 6 Session 1 (bd9e734), seed list. "emergency" intentionally
#   excluded — over-triggers on legitimate intake speech like
#   "I left during the emergency".
# - ES/AR/FA: Day 10 Session 2 — translated via scripts/translate_safety_keywords.py
#   (untracked) using the working two-model pipeline, then human-reviewed
#   with five idiomatic corrections applied:
#     * ES "going to hurt"   → voy a hacerle daño   (was: va a doler)
#     * ES "going to kill"   → voy a matar          (was: ir a matar)
#     * ES "going to attack" → voy a atacar         (was: yendo a atacar)
#     * AR "end my life" — both اقتلني (kill me, addressed-to-other) AND
#                          أنهي حياتي (I end my life, self-directed)
#     * FA "going to hurt"   → می‌خواهم آسیب بزنم  (was: قرار است آسیب ببیند)
#   Mixed-register FA (می‌خوام colloquial vs می‌خواهم formal) is intentional —
#   covers naturalistic speech variation in displaced-person voice notes.
# - FR/UK: Day 10 Session 5 — translated via scripts/expand_languages.py
#   (untracked) using the same two-model pipeline. Human review applied
#   six corrections to FR (first-person register consistency with ES) and
#   one to UK (verb-of-motion fix):
#     * FR "end my life"     → mettre fin à ma vie    (was: tuer)
#     * FR "want to die"     → je veux mourir         (was: vouloir mourir)
#     * FR "going to hurt"   → je vais faire mal      (was: aller faire mal)
#     * FR "going to kill"   → je vais tuer           (was: aller tuer)
#     * FR "going to attack" → je vais attaquer       (was: aller attaquer)
#     * UK "going to attack" → збираюся атакувати     (was: їду атакувати,
#                                                      "I am riding to attack")
#   Six expansion candidates (sw/am/so/ps/bn/ti) dropped on defensibility
#   grounds — see results/language_expansion_baseline_20260427_003403.md.
#   The Bengali drop in particular surfaces a Whisper-medium failure mode:
#   80-105s degenerate-decoder loops on bn audio across 4 clips.
_CRISIS_KEYWORDS: dict[SupportedLang, frozenset[str]] = {
    "en": frozenset(
        {
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
            # Immediate-danger context
            "immediate danger",
        }
    ),
    "es": frozenset(
        {
            "me suicido",
            "acabar mi vida",
            "suicidio",
            "quiero morir",
            "hacerme daño",
            "voy a hacerle daño",
            "voy a matar",
            "voy a atacar",
            "peligro inminente",
        }
    ),
    "ar": frozenset(
        {
            "أقتل نفسي",
            "اقتلني",
            "أنهي حياتي",
            "انتحار",
            "أريد أن أموت",
            "أجرح نفسي",
            "سوف يؤلم",
            "سأقتل",
            "سوف نهاجم",
            "خطر وشيك",
        }
    ),
    "fa": frozenset(
        {
            "خودم را بکشم",
            "زندگی‌ام را تمام کن",
            "خودکشی",
            "می‌خوام بمیرم",
            "خودم را آزار بده",
            "می‌خواهم آسیب بزنم",
            "می‌خواهم بکشم",
            "می‌خواهم حمله کنم",
            "خطر فوری",
        }
    ),
    "fr": frozenset(
        {
            "me suicider",
            "mettre fin à ma vie",
            "suicide",
            "je veux mourir",
            "me faire mal",
            "je vais faire mal",
            "je vais tuer",
            "je vais attaquer",
            "danger immédiat",
        }
    ),
    "uk": frozenset(
        {
            "вбити себе",
            "закінчити моє життя",
            "самогубство",
            "хочу померти",
            "зашкоди собі",
            "буде боляче",
            "йти вбивати",
            "збираюся атакувати",
            "небезпека негайна",
        }
    ),
}


def classify(text: str, lang: str = "en") -> SafetyResult:
    """Scan `text` for known crisis keywords in `lang`.

    Returns is_crisis=True with block_intake suggestion on any
    substring match. For unimplemented languages keeps the original
    permissive default — safer to log and proceed than to false-
    positive block intake on a language whose keyword list isn't
    wired up yet. Cap at 5000 chars; intake utterances are typically
    <500 chars, longer inputs are likely corrupt or adversarial.
    """
    if lang not in IMPLEMENTED_LANGS:
        return SafetyResult(
            is_crisis=False,
            matched_keywords=[],
            suggested_action="proceed",
            crisis_resources_locale=None,
        )

    haystack = text[:5000].lower()
    keywords = _CRISIS_KEYWORDS[lang]  # type: ignore[index]
    matched = sorted(kw for kw in keywords if kw in haystack)
    if matched:
        return SafetyResult(
            is_crisis=True,
            matched_keywords=matched,
            suggested_action="block_intake",
            crisis_resources_locale=lang,
        )
    return SafetyResult(
        is_crisis=False,
        matched_keywords=[],
        suggested_action="proceed",
        crisis_resources_locale=None,
    )
