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

from core.rfl_schema import Age, FamilyMember, LastSeen, Name, RFLRecord

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


class NodeMatch(BaseModel):
    """A single name-pair comparison between two RFLRecord nodes.

    role_a/role_b identify which slot each name belongs to in its
    respective record. roster_index_a/b are set only when role is
    roster_member. composite_score includes the SAME_SCRIPT_EXACT_FLOOR
    so sparse roster members (no age, no last_seen) still surface when
    phonetic score is 1.0.
    """

    role_a: Literal["searcher", "missing_person", "roster_member"]
    role_b: Literal["searcher", "missing_person", "roster_member"]
    name_a: str
    name_b: str
    roster_index_a: int | None = None
    roster_index_b: int | None = None
    phonetic_score: float
    composite_score: float


class NetworkMatchResult(BaseModel):
    """Cross-role family-network comparison result.

    matched=True when at least one NodeMatch pair passed both gates.
    node_matches sorted by composite_score descending.
    primary_match == node_matches[0] when matched=True, else None.
    """

    matched: bool
    node_matches: list[NodeMatch] = []
    primary_match: NodeMatch | None = None


# Mirrors transcription_pipeline._LANG_TO_SOURCE_SCRIPT. Inlined here
# so Core stays free of Integration imports. Update both if new language
# codes are added.
_NETWORK_LANG_TO_SCRIPT: dict[str, str] = {
    "en": "latin",
    "es": "latin",
    "fr": "latin",
    "ar": "arabic",
    "fa": "persian",
    "uk": "cyrillic",
}


def _name_for_str(
    s: str,
    source_script: str,
    transliteration: str | None = None,
) -> Name:
    """Wrap a plain string in a Name for cross-role comparison.

    source_script is inferred from the record's primary name when
    available. transliteration is included when the caller has a
    separate Latin form (e.g. searcher_name_transliteration).
    """
    return Name(
        canonical=s,
        source_script=source_script,  # type: ignore[arg-type]
        transliterations=[transliteration] if transliteration else [],
    )


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


# Public alias so transcription_pipeline.py can call this without
# importing a _-prefixed symbol from another module.
confidence_band_for_score = _confidence_band


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


def match_records_network(a: RFLRecord, b: RFLRecord) -> NetworkMatchResult:
    """Compare two RFLRecords across all cross-role name pairs.

    Enumerates seven pair types:
      1. searcher(a)      ↔ missing_person(b)
      2. missing_person(a) ↔ searcher(b)
      3. roster(a)[i]     ↔ missing_person(b)
      4. missing_person(a) ↔ roster(b)[j]
      5. searcher(a)      ↔ roster(b)[j]
      6. roster(a)[i]     ↔ searcher(b)
      7. roster(a)[i]     ↔ roster(b)[j]

    Each pair applies the two-stage gate: phonetic ≥ GATE_THRESHOLD then
    composite ≥ COMPOSITE_THRESHOLD. Marks score is always 0.0
    (FamilyMember has no distinguishing_marks); SAME_SCRIPT_EXACT_FLOOR
    floors composite at 0.85 when phonetic=1.0, rescuing sparse roster
    members with only a name.

    Pure-Core. No I/O, no LLM.
    """
    script_a: str = a.name.source_script if a.name else "latin"
    script_b: str = b.name.source_script if b.name else "latin"

    passing: list[NodeMatch] = []

    def _eval(
        name_a: Name | None,
        name_b: Name | None,
        role_a: str,
        role_b: str,
        raw_a: str,
        raw_b: str,
        age_a: Age | None,
        age_b: Age | None,
        last_seen_a: LastSeen | None,
        last_seen_b: LastSeen | None,
        idx_a: int | None,
        idx_b: int | None,
    ) -> None:
        phonetic, _ = _phonetic_name_match(name_a, name_b)
        if phonetic < GATE_THRESHOLD:
            return
        composite = _composite(
            phonetic,
            _score_age(age_a, age_b),
            _score_last_seen(last_seen_a, last_seen_b),
            0.0,
        )
        if composite < COMPOSITE_THRESHOLD:
            return
        passing.append(NodeMatch(
            role_a=role_a,  # type: ignore[arg-type]
            role_b=role_b,  # type: ignore[arg-type]
            name_a=raw_a,
            name_b=raw_b,
            roster_index_a=idx_a,
            roster_index_b=idx_b,
            phonetic_score=phonetic,
            composite_score=composite,
        ))

    def _roster_age(m: FamilyMember) -> Age | None:
        return Age(value=m.age, confidence="exact") if m.age is not None else None

    def _roster_last_seen(m: FamilyMember) -> LastSeen | None:
        return LastSeen(location=m.last_seen_location) if m.last_seen_location else None

    # 1. searcher(a) ↔ missing_person(b)
    if a.searcher_name and b.name:
        _eval(
            _name_for_str(a.searcher_name, script_a, a.searcher_name_transliteration),
            b.name,
            "searcher", "missing_person",
            a.searcher_name, b.name.canonical,
            None, b.age, None, b.last_seen, None, None,
        )

    # 2. missing_person(a) ↔ searcher(b)
    if a.name and b.searcher_name:
        _eval(
            a.name,
            _name_for_str(b.searcher_name, script_b, b.searcher_name_transliteration),
            "missing_person", "searcher",
            a.name.canonical, b.searcher_name,
            a.age, None, a.last_seen, None, None, None,
        )

    # 3. roster_member(a)[i] ↔ missing_person(b)
    if b.name:
        for i, m in enumerate(a.family_roster):
            _eval(
                _name_for_str(m.name, script_a, m.name_transliteration),
                b.name,
                "roster_member", "missing_person",
                m.name, b.name.canonical,
                _roster_age(m), b.age,
                _roster_last_seen(m), b.last_seen,
                i, None,
            )

    # 4. missing_person(a) ↔ roster_member(b)[j]
    if a.name:
        for j, m in enumerate(b.family_roster):
            _eval(
                a.name,
                _name_for_str(m.name, script_b, m.name_transliteration),
                "missing_person", "roster_member",
                a.name.canonical, m.name,
                a.age, _roster_age(m),
                a.last_seen, _roster_last_seen(m),
                None, j,
            )

    # 5. searcher(b) ↔ roster_member(a)[i]  (symmetric of path 3)
    if a.searcher_name:
        for i, m in enumerate(b.family_roster):
            _eval(
                _name_for_str(
                    a.searcher_name, script_a, a.searcher_name_transliteration
                ),
                _name_for_str(m.name, script_b, m.name_transliteration),
                "searcher", "roster_member",
                a.searcher_name, m.name,
                None, _roster_age(m),
                None, _roster_last_seen(m),
                None, i,
            )

    # 6. roster_member(a)[i] ↔ searcher(b)  (symmetric of path 1)
    if b.searcher_name:
        for i, m in enumerate(a.family_roster):
            _eval(
                _name_for_str(m.name, script_a, m.name_transliteration),
                _name_for_str(
                    b.searcher_name, script_b, b.searcher_name_transliteration
                ),
                "roster_member", "searcher",
                m.name, b.searcher_name,
                _roster_age(m), None,
                _roster_last_seen(m), None,
                i, None,
            )

    # 7. roster_member(a)[i] ↔ roster_member(b)[j]
    for i, ma in enumerate(a.family_roster):
        for j, mb in enumerate(b.family_roster):
            _eval(
                _name_for_str(ma.name, script_a, ma.name_transliteration),
                _name_for_str(mb.name, script_b, mb.name_transliteration),
                "roster_member", "roster_member",
                ma.name, mb.name,
                _roster_age(ma), _roster_age(mb),
                _roster_last_seen(ma), _roster_last_seen(mb),
                i, j,
            )

    if not passing:
        return NetworkMatchResult(matched=False)

    passing.sort(key=lambda n: n.composite_score, reverse=True)
    return NetworkMatchResult(
        matched=True,
        node_matches=passing,
        primary_match=passing[0],
    )
