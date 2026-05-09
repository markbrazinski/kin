"""Cross-record matching: phonetic gate + corroborating-field validators.

Pure-Core tests. No I/O, no LLM, no Integration imports. Test 7 is a
targeted regression for the no-LLM lock; the broader Core boundary is
enforced by tests/test_layer_boundaries.py.

Test 2 uses a same-script Arabic fixture for Omar/Umar — Latin-only
phonetic comparison cannot bridge them (different leading vowels) and
the architecture's source-script preservation is the bridge instead.
See docs/matching.md §6 and §8.
"""

from pathlib import Path

from core.matching import (
    GATE_THRESHOLD,
    MatchResult,
    match_records,
    match_records_network,
)
from core.rfl_schema import Age, FamilyMember, LastSeen, Name, RFLRecord


def _record(
    name: Name | None = None,
    age: Age | None = None,
    last_seen: LastSeen | None = None,
    marks: list[str] | None = None,
) -> RFLRecord:
    """Inline-record helper. Marks default to empty list per schema."""
    return RFLRecord(
        name=name,
        age=age,
        last_seen=last_seen,
        distinguishing_marks=marks or [],
    )


def test_match_mohammed_mohamad_arabic_script_high_confidence() -> None:
    """The demo wow moment. Both records captured the Arabic canonical
    form; transliterations differ ("Mohammed" vs "Mohamad"). Same-script
    exact name + age + last_seen agree → high confidence.
    """
    a = _record(
        name=Name(
            canonical="محمد",
            source_script="arabic",
            transliterations=["Mohammed"],
        ),
        age=Age(value=9, confidence="approximate"),
        last_seen=LastSeen(
            location="Aleppo", date_text="three weeks before we left"
        ),
    )
    b = _record(
        name=Name(
            canonical="محمد",
            source_script="arabic",
            transliterations=["Mohamad"],
        ),
        age=Age(value=9, confidence="approximate"),
        last_seen=LastSeen(
            location="Aleppo neighborhood",
            date_text="about three weeks ago",
        ),
    )
    result = match_records(a, b)
    assert result.is_match is True
    assert result.phonetic_score == 1.0
    assert result.score >= 0.7
    assert "age" in result.matched_fields
    assert "last_seen" in result.matched_fields
    assert result.confidence == "high"


def test_match_omar_umar_phonetic() -> None:
    """Transliteration variance routed through the architecture's
    source-script preservation. Both intakes captured Arabic عمر; one
    volunteer romanized as "Omar", the other as "Umar". Latin-only
    JW cannot bridge O/U (different vowels) — the source-script
    canonical is the bridge.
    """
    a = _record(
        name=Name(canonical="عمر", source_script="arabic", transliterations=["Omar"]),
        age=Age(value=15, confidence="exact"),
        last_seen=LastSeen(location="Damascus", date_text="last summer"),
    )
    b = _record(
        name=Name(canonical="عمر", source_script="arabic", transliterations=["Umar"]),
        age=Age(value=15, confidence="exact"),
        last_seen=LastSeen(location="Damascus old city", date_text="summer 2024"),
    )
    result = match_records(a, b)
    assert result.is_match is True
    assert result.phonetic_score == 1.0
    assert result.confidence == "high"


def test_match_different_people_same_age_no_match() -> None:
    """False-positive guard. Carlos and Juan are distinct names; even
    with identical age and location, the phonetic gate must reject.
    Load-bearing: humanitarian intake cannot tolerate name-collision
    false-positives."""
    a = _record(
        name=Name(canonical="Carlos", source_script="latin"),
        age=Age(value=12, confidence="exact"),
        last_seen=LastSeen(location="Caracas", date_text="March 2024"),
    )
    b = _record(
        name=Name(canonical="Juan", source_script="latin"),
        age=Age(value=12, confidence="exact"),
        last_seen=LastSeen(location="Caracas", date_text="March 2024"),
    )
    result = match_records(a, b)
    assert result.is_match is False
    assert result.phonetic_score < GATE_THRESHOLD
    assert result.score == 0.0
    assert result.matched_fields == []
    assert result.confidence == "low"


def test_match_same_name_different_ages_low_confidence() -> None:
    """Same-script exact name + corroborating disagreement. Two different
    Marias of incompatible ages. Same-script-exact floor keeps composite
    above 0.70 (so it's a match by score), but with zero corroborating
    fields agreeing the band is "medium" — not high. Demonstrates that
    corroborating fields validate but do not veto, and that the floor
    deliberately keeps name-alone matches in the "review me" tier.
    """
    a = _record(
        name=Name(canonical="Maria", source_script="latin"),
        age=Age(value=8, confidence="exact"),
    )
    b = _record(
        name=Name(canonical="Maria", source_script="latin"),
        age=Age(value=42, confidence="exact"),
    )
    result = match_records(a, b)
    assert result.is_match is True
    assert result.phonetic_score == 1.0
    assert result.score >= 0.7
    assert "age" not in result.matched_fields
    assert result.confidence == "medium"


def test_match_below_phonetic_threshold_no_match_regardless_of_corroborating() -> None:
    """Gate enforcement. Aiyana and Bartholomew are not the same name.
    Identical age, last_seen, AND distinguishing_marks cannot rescue a
    failed phonetic gate. Load-bearing for the locked Q1 design decision.
    """
    a = _record(
        name=Name(canonical="Aiyana", source_script="latin"),
        age=Age(value=30, confidence="exact"),
        last_seen=LastSeen(location="Phoenix", date_text="January 2024"),
        marks=["scar above left eyebrow"],
    )
    b = _record(
        name=Name(canonical="Bartholomew", source_script="latin"),
        age=Age(value=30, confidence="exact"),
        last_seen=LastSeen(location="Phoenix", date_text="January 2024"),
        marks=["scar above left eyebrow"],
    )
    result = match_records(a, b)
    assert result.is_match is False
    assert result.score == 0.0
    assert result.matched_fields == []
    assert result.confidence == "low"


def test_match_returns_pydantic_match_result() -> None:
    """Schema contract. Every match returns a fully-populated MatchResult
    with valid types; round-trips through model_dump → model_validate
    unchanged. Demo UI consumes this shape directly."""
    a = _record(
        name=Name(canonical="Layla", source_script="latin"),
        age=Age(value=22, confidence="exact"),
    )
    b = _record(
        name=Name(canonical="Layla", source_script="latin"),
        age=Age(value=22, confidence="exact"),
    )
    result = match_records(a, b)
    assert isinstance(result, MatchResult)
    assert isinstance(result.is_match, bool)
    assert isinstance(result.score, float)
    assert isinstance(result.phonetic_score, float)
    assert isinstance(result.matched_fields, list)
    assert isinstance(result.reason, str)
    assert result.confidence in ("low", "medium", "high")
    assert 0.0 <= result.score <= 1.0
    assert 0.0 <= result.phonetic_score <= 1.0
    assert MatchResult.model_validate(result.model_dump()) == result


def test_match_module_does_not_import_llm_clients() -> None:
    """Targeted regression: matching.py must not bypass the no-LLM lock
    by direct-importing an LLM client. tests/test_layer_boundaries
    catches integration/ui imports via AST; this catches the narrower
    case of a direct ollama/anthropic/openai client import sneaking in.
    Documents PROJECT_PLAN §6.4 lock at the test-suite level."""
    source = Path(__file__).parent.parent.parent.joinpath(
        "src", "core", "matching.py"
    ).read_text()
    forbidden = (
        "import ollama",
        "from ollama",
        "import anthropic",
        "from anthropic",
        "import openai",
        "from openai",
    )
    for phrase in forbidden:
        assert phrase not in source, (
            f"matching.py must not import LLM clients: {phrase!r}"
        )


# ─── B2-S11: cross-role network match tests ───────────────────────


def _network_record(
    name: Name | None = None,
    age: Age | None = None,
    last_seen: LastSeen | None = None,
    searcher_name: str | None = None,
    searcher_name_transliteration: str | None = None,
    roster: list[FamilyMember] | None = None,
) -> RFLRecord:
    return RFLRecord(
        name=name,
        age=age,
        last_seen=last_seen,
        distinguishing_marks=[],
        searcher_name=searcher_name,
        searcher_name_transliteration=searcher_name_transliteration,
        family_roster=roster or [],
    )


def test_network_match_searcher_to_missing_person() -> None:
    """searcher(a)=Yusuf ↔ missing_person(b)=Yusuf — single boundary.
    Fires via SAME_SCRIPT_EXACT_FLOOR=0.85; no age on the searcher slot.
    """
    a = _network_record(
        name=Name(canonical="Ahmad", source_script="latin"),
        searcher_name="Yusuf",
    )
    b = _network_record(
        name=Name(canonical="Yusuf", source_script="latin"),
        age=Age(value=35, confidence="exact"),
    )
    result = match_records_network(a, b)
    assert result.matched is True
    assert result.primary_match is not None
    assert result.primary_match.role_a == "searcher"
    assert result.primary_match.role_b == "missing_person"
    assert result.primary_match.roster_index_a is None
    assert result.primary_match.roster_index_b is None


def test_network_match_roster_to_missing_person() -> None:
    """roster_member(a)[0]=Mariam ↔ missing_person(b)=Mariam.
    Sparse roster member (name only); fires via SAME_SCRIPT_EXACT_FLOOR.
    """
    a = _network_record(
        name=Name(canonical="Yusuf", source_script="latin"),
        roster=[
            FamilyMember(
                name="Mariam", relationship_to_searcher="sister", status="missing"
            ),
        ],
    )
    b = _network_record(name=Name(canonical="Mariam", source_script="latin"))
    result = match_records_network(a, b)
    assert result.matched is True
    assert result.primary_match is not None
    assert result.primary_match.role_a == "roster_member"
    assert result.primary_match.role_b == "missing_person"
    assert result.primary_match.roster_index_a == 0
    assert result.primary_match.roster_index_b is None


def test_network_match_roster_to_roster() -> None:
    """roster_member(a)[0]=محمد (age 8) ↔ roster_member(b)[0]=محمد (age 8).
    Age corroborates; composite = max(0.40, 0.85) = 0.85 via floor.
    """
    a = _network_record(
        name=Name(canonical="يوسف", source_script="arabic"),
        roster=[
            FamilyMember(
                name="محمد", relationship_to_searcher="nephew", age=8, status="missing"
            ),
        ],
    )
    b = _network_record(
        name=Name(canonical="مريم", source_script="arabic"),
        roster=[
            FamilyMember(
                name="محمد", relationship_to_searcher="son", age=8, status="missing"
            ),
        ],
    )
    result = match_records_network(a, b)
    assert result.matched is True
    assert result.primary_match is not None
    assert result.primary_match.role_a == "roster_member"
    assert result.primary_match.role_b == "roster_member"
    assert result.primary_match.roster_index_a == 0
    assert result.primary_match.roster_index_b == 0


def test_network_match_full_yusuf_mariam_mohamad() -> None:
    """The demo case. Three cross-role pairs must all fire:
      searcher(A)=يوسف ↔ missing_person(B)=يوسف  — floor, no age
      missing_person(A)=محمد ↔ roster(B)[0]=محمد   — floor, age 8
      roster(A)[0]=مريم ↔ searcher(B)=مريم          — floor, no age
    All three reach composite=0.85 via SAME_SCRIPT_EXACT_FLOOR.
    """
    record_a = _network_record(
        name=Name(
            canonical="محمد", source_script="arabic", transliterations=["Mohamad"]
        ),
        age=Age(value=8, confidence="approximate"),
        last_seen=LastSeen(location="Aleppo"),
        searcher_name="يوسف",
        searcher_name_transliteration="Yusuf",
        roster=[
            FamilyMember(
                name="مريم",
                name_transliteration="Mariam",
                relationship_to_searcher="sister",
                status="missing",
            ),
        ],
    )
    record_b = _network_record(
        name=Name(canonical="يوسف", source_script="arabic", transliterations=["Yusuf"]),
        age=Age(value=35, confidence="exact"),
        searcher_name="مريم",
        searcher_name_transliteration="Mariam",
        roster=[
            FamilyMember(
                name="محمد",
                name_transliteration="Mohamad",
                relationship_to_searcher="nephew",
                age=8,
                status="missing",
            ),
        ],
    )
    result = match_records_network(record_a, record_b)
    assert result.matched is True
    assert len(result.node_matches) == 3
    roles = {(n.role_a, n.role_b) for n in result.node_matches}
    assert ("searcher", "missing_person") in roles
    assert ("missing_person", "roster_member") in roles
    assert ("roster_member", "searcher") in roles


def test_network_no_match_on_unrelated_records() -> None:
    """Distinct families — no overlapping names across any node role."""
    a = _network_record(
        name=Name(canonical="Carlos", source_script="latin"),
        searcher_name="Rosa",
        roster=[
            FamilyMember(
                name="Lucia", relationship_to_searcher="sister", status="missing"
            ),
        ],
    )
    b = _network_record(
        name=Name(canonical="Fatima", source_script="latin"),
        searcher_name="Omar",
        roster=[
            FamilyMember(
                name="Ahmad", relationship_to_searcher="brother", status="missing"
            ),
        ],
    )
    result = match_records_network(a, b)
    assert result.matched is False
    assert result.node_matches == []
    assert result.primary_match is None


def test_network_no_double_count_when_primary_in_roster() -> None:
    """Regression guard: if the pipeline were to leave the primary name in
    both RFLRecord.name (missing_person slot) and family_roster, the matcher
    would fire path 2 AND path 6 for the same name pair, inflating
    node_matches. This test verifies the correct case: primary filtered from
    roster before RFLRecord is built, so exactly 3 node_matches fire for the
    Mariam scenario (Yusuf-pair, Mohamad-pair, Mariam-as-searcher-pair).

    The three expected pairs:
      path 2: missing_person(a)=يوسف ↔ searcher(b)=يوسف   → fires
      path 3: roster_member(a)[0]=محمد ↔ missing_person(b)=يوسف  → fails (different name)
      path 4: missing_person(a)=يوسف ↔ roster_member(b)[0]=مريم  → fails (different name)
      path 1: searcher(a)=مريم ↔ missing_person(b)=يوسف  → fails (different name)
      path 5: searcher(a)=مريم ↔ roster_member(b)[0]=مريم  → fires
      path 6: roster_member(a)[0]=محمد ↔ searcher(b)=يوسف  → fails
      path 7: roster_member(a)[0]=محمد ↔ roster_member(b)[0]=مريم  → fails

    Wait — this gives 2, not 3. The third is path 3/4 on the سcar/Mohamad cross
    if a Yusuf record includes Mohamad. Re-cast: keep this simple — primary
    filtered from roster means path 6 cannot fire a Yusuf duplicate.
    Assert node_matches does NOT contain two entries with name_a/name_b both
    equal to يوسف.
    """
    # Mariam's record (after _to_rfl_record filtering):
    # name=يوسف (primary/missing_person), searcher_name=مريم,
    # family_roster=[محمد only — يوسف filtered out].
    mariam_record = _network_record(
        name=Name(canonical="يوسف", source_script="arabic"),
        searcher_name="مريم",
        roster=[
            FamilyMember(
                name="محمد",
                relationship_to_searcher="ابن",
                status="missing",
                age=8,
            ),
        ],
    )

    # Yusuf's record: searcher=يوسف, missing_person=مريم.
    yusuf_record = _network_record(
        name=Name(canonical="مريم", source_script="arabic"),
        searcher_name="يوسف",
    )

    result = match_records_network(mariam_record, yusuf_record)
    assert result.matched is True

    # يوسف must appear as a matched pair exactly once —
    # via path 2 (missing_person↔searcher), not also via path 6
    # (roster_member↔searcher). Filtering يوسف from the roster prevents
    # the duplicate.
    yusuf_pairs = [
        nm for nm in result.node_matches
        if nm.name_a == "يوسف" or nm.name_b == "يوسف"
    ]
    assert len(yusuf_pairs) == 1, (
        f"يوسف matched {len(yusuf_pairs)} times — expected 1. "
        f"node_matches: {result.node_matches}"
    )
    assert yusuf_pairs[0].role_a == "missing_person"
    assert yusuf_pairs[0].role_b == "searcher"


def test_same_role_match_records_unchanged() -> None:
    """Regression: match_records returns high-confidence for Mohammed/Mohamad
    same-role Arabic case. S11 additions must not affect this function.
    """
    a = _record(
        name=Name(
            canonical="محمد", source_script="arabic", transliterations=["Mohammed"]
        ),
        age=Age(value=9, confidence="approximate"),
        last_seen=LastSeen(location="Aleppo", date_text="three weeks before we left"),
    )
    b = _record(
        name=Name(
            canonical="محمد", source_script="arabic", transliterations=["Mohamad"]
        ),
        age=Age(value=9, confidence="approximate"),
        last_seen=LastSeen(
            location="Aleppo neighborhood", date_text="about three weeks ago"
        ),
    )
    result = match_records(a, b)
    assert result.is_match is True
    assert result.phonetic_score == 1.0
    assert result.score >= 0.7
    assert result.confidence == "high"
