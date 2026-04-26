"""Phonetic-gated record matching with corroborating-field scoring.

Pure Core. No I/O, no LLM, no Integration imports — enforced by
tests/test_layer_boundaries.py and tests/core/test_matching.py
(test_match_module_does_not_import_llm_clients). Single responsibility:
given two RFLRecords, decide whether they describe the same person and
produce a MatchResult the demo UI can render.

Two-stage by design (PROJECT_PLAN §6.4 lock; see docs/matching.md):
  1. Phonetic name gate — Jaro-Winkler on the right name pair selected
     by source_script. Below GATE_THRESHOLD, no match regardless of
     corroborating evidence. Strong corroborating cannot manufacture
     identity from a weak name match.
  2. Corroborating scoring — Age, LastSeen, distinguishing_marks
     contribute to a composite score above the gate. Same-script-exact
     name floors the composite at 0.85 so a bare-name match still
     produces a usable score in the "review me" tier.
"""

from __future__ import annotations

import re
from typing import Literal

import jellyfish
from pydantic import BaseModel

from core.rfl_schema import Age, LastSeen, Name, RFLRecord

GATE_THRESHOLD: float = 0.85
COMPOSITE_THRESHOLD: float = 0.70
AMBIGUOUS_BAND: tuple[float, float] = (0.65, 0.75)

WEIGHT_AGE: float = 0.40
WEIGHT_LAST_SEEN: float = 0.40
WEIGHT_MARKS: float = 0.20

AGE_EXACT: float = 1.0
AGE_NEAR_2Y: float = 0.7
AGE_NEAR_5Y: float = 0.3

SAME_SCRIPT_EXACT_FLOOR: float = 0.85

ConfidenceBand = Literal["low", "medium", "high"]

_ASCII_ALPHA = re.compile(r"[A-Za-z]")
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


class MatchResult(BaseModel):
    """Result of comparing two RFLRecords.

    Demo UI consumes this to render the linked-record card. `reason`
    feeds the trace panel; `phonetic_score` is exposed separately from
    `score` so the UI can show "name evidence" and "field evidence" as
    orthogonal axes (see docs/matching.md §4).
    """

    is_match: bool
    score: float
    phonetic_score: float
    matched_fields: list[str]
    confidence: ConfidenceBand
    reason: str


def _has_ascii_alpha(s: str) -> bool:
    return bool(_ASCII_ALPHA.search(s))


def _phonetic_name_match(a: Name | None, b: Name | None) -> tuple[float, bool]:
    """Score the phonetic name pair and report same-script-exact status.

    Returns (jw_score, same_script_exact). Same-script identical canonical
    short-circuits to 1.0; cross-script enumerates canonical+transliteration
    pairs (skipping those without ASCII alpha on either side) and takes
    the max JW. Best-pair wins because identity is yes/no — averaging in
    weak pairs would dilute a real signal.
    """
    if a is None or b is None:
        return (0.0, False)

    if a.source_script == b.source_script:
        if a.canonical == b.canonical:
            return (1.0, True)
        return (jellyfish.jaro_winkler_similarity(a.canonical, b.canonical), False)

    # Cross-script: enumerate canonical + transliterations on both sides.
    candidates_a = [a.canonical, *a.transliterations]
    candidates_b = [b.canonical, *b.transliterations]
    best = 0.0
    scored_any = False
    for x in candidates_a:
        for y in candidates_b:
            if not (_has_ascii_alpha(x) and _has_ascii_alpha(y)):
                continue
            scored_any = True
            score = jellyfish.jaro_winkler_similarity(x, y)
            if score > best:
                best = score
    if scored_any:
        return (best, False)
    # No usable pair (e.g. arabic canonical, no transliterations on either
    # side). Best-effort fallback so we never silently drop the comparison.
    return (jellyfish.jaro_winkler_similarity(a.canonical, b.canonical), False)


def _score_age(a: Age | None, b: Age | None) -> float:
    """Bucketed age agreement. Unknown confidence or missing value → 0.0
    (no signal). Exact → 1.0; ±2y → 0.7; ±5y → 0.3; else 0.0."""
    if a is None or b is None:
        return 0.0
    if a.value is None or b.value is None:
        return 0.0
    if a.confidence == "unknown" or b.confidence == "unknown":
        return 0.0
    diff = abs(a.value - b.value)
    if diff == 0:
        return AGE_EXACT
    if diff <= 2:
        return AGE_NEAR_2Y
    if diff <= 5:
        return AGE_NEAR_5Y
    return 0.0


def _tokens(s: str, min_len: int) -> set[str]:
    return {
        t
        for t in (m.group(0) for m in _TOKEN.finditer(s.lower()))
        if len(t) >= min_len
    }


def _strings_overlap(x: str | None, y: str | None, min_len: int) -> bool:
    if not x or not y:
        return False
    return bool(_tokens(x, min_len) & _tokens(y, min_len))


def _score_last_seen(a: LastSeen | None, b: LastSeen | None) -> float:
    """Substring-token overlap on location and date_text (≥4 chars,
    case-folded). Both overlap → 1.0; one → 0.5; neither → 0.0."""
    if a is None or b is None:
        return 0.0
    loc = _strings_overlap(a.location, b.location, min_len=4)
    date = _strings_overlap(a.date_text, b.date_text, min_len=4)
    if loc and date:
        return 1.0
    if loc or date:
        return 0.5
    return 0.0


def _score_marks(a: list[str], b: list[str]) -> float:
    """Binary tiebreaker. Any ≥5-char token from any mark in a appears
    in any mark in b (case-folded) → 1.0; else 0.0."""
    if not a or not b:
        return 0.0
    tokens_a: set[str] = set()
    for mark in a:
        tokens_a |= _tokens(mark, min_len=5)
    if not tokens_a:
        return 0.0
    for mark in b:
        if tokens_a & _tokens(mark, min_len=5):
            return 1.0
    return 0.0


def _composite(phonetic: float, age: float, last_seen: float, marks: float) -> float:
    """Weighted sum of corroborating fields. Phonetic does NOT enter
    the sum (the gate already enforced it; double-counting would drown
    the corroborating signal). Same-script-exact phonetic floors the
    composite at SAME_SCRIPT_EXACT_FLOOR so bare-name matches still
    surface in the "review me" tier."""
    composite = WEIGHT_AGE * age + WEIGHT_LAST_SEEN * last_seen + WEIGHT_MARKS * marks
    if phonetic == 1.0:
        composite = max(composite, SAME_SCRIPT_EXACT_FLOOR)
    return min(composite, 1.0)


def _confidence_band(
    phonetic: float,
    same_script_exact: bool,
    num_corroborating: int,
    composite: float,
) -> ConfidenceBand:
    """Disambiguated confidence rules (see docs/matching.md §5).

    Order matters: the ambiguous-band demotion runs before the positive
    bands so a borderline composite never overclaims, and gate failure
    is handled before any other rule fires.
    """
    if phonetic < GATE_THRESHOLD:
        return "low"
    if AMBIGUOUS_BAND[0] <= composite <= AMBIGUOUS_BAND[1]:
        return "low"
    if same_script_exact and num_corroborating >= 1:
        return "high"
    if same_script_exact:
        return "medium"
    if num_corroborating >= 1:
        return "medium"
    return "low"


def _build_reason(
    phonetic: float,
    same_script_exact: bool,
    matched_fields: list[str],
    composite: float,
) -> str:
    """Human-readable explanation for the demo trace panel."""
    if phonetic < GATE_THRESHOLD:
        return f"name phonetic {phonetic:.2f} below gate {GATE_THRESHOLD:.2f}"
    name_part = (
        "same-script exact name"
        if same_script_exact
        else f"phonetic name match {phonetic:.2f}"
    )
    if matched_fields:
        fields = ", ".join(matched_fields)
        return f"{name_part}; {fields} agree (composite {composite:.2f})"
    return f"{name_part}; no corroborating fields agree (composite {composite:.2f})"


def match_records(a: RFLRecord, b: RFLRecord) -> MatchResult:
    """Compare two RFLRecords and return a MatchResult.

    Two-stage: phonetic gate at GATE_THRESHOLD, then corroborating-
    field composite at COMPOSITE_THRESHOLD. Pure-Core, deterministic,
    no LLM in the path. PROJECT_PLAN §6.4.
    """
    phonetic, same_script_exact = _phonetic_name_match(a.name, b.name)

    if phonetic < GATE_THRESHOLD:
        return MatchResult(
            is_match=False,
            score=0.0,
            phonetic_score=phonetic,
            matched_fields=[],
            confidence="low",
            reason=_build_reason(phonetic, same_script_exact, [], 0.0),
        )

    age_score = _score_age(a.age, b.age)
    last_seen_score = _score_last_seen(a.last_seen, b.last_seen)
    marks_score = _score_marks(a.distinguishing_marks, b.distinguishing_marks)

    matched_fields = [
        name
        for name, score in (
            ("age", age_score),
            ("last_seen", last_seen_score),
            ("distinguishing_marks", marks_score),
        )
        if score > 0.0
    ]

    composite = _composite(phonetic, age_score, last_seen_score, marks_score)
    is_match = composite >= COMPOSITE_THRESHOLD
    confidence = _confidence_band(
        phonetic, same_script_exact, len(matched_fields), composite
    )
    reason = _build_reason(phonetic, same_script_exact, matched_fields, composite)

    return MatchResult(
        is_match=is_match,
        score=composite,
        phonetic_score=phonetic,
        matched_fields=matched_fields,
        confidence=confidence,
        reason=reason,
    )
