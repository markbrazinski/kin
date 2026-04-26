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
)
from core.rfl_schema import Age, LastSeen, Name, RFLRecord


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
