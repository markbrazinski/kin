"""Structural tests for RFLRecord and its sub-models (Day 6 Session 3).

Three tests prove the schema's structural invariants. Field-semantic
tests (e.g., "transliterations should not be empty for arabic
source_script") are matching-layer concerns and live elsewhere.

B2-S9 additions: four tests for FamilyMember and the extended RFLRecord
fields (family_roster, searcher_*).
"""

import pytest
from pydantic import ValidationError

from core.rfl_schema import (
    Age,
    FamilyMember,
    Guardian,
    LastSeen,
    Name,
    RFLRecord,
)


def test_rfl_record_round_trips_full_payload() -> None:
    """A fully-populated RFLRecord serialized via model_dump() and
    reconstructed via model_validate() must compare equal. Proves
    the schema is internally consistent across the round trip.
    """
    record = RFLRecord(
        name=Name(
            canonical="محمد",
            source_script="arabic",
            transliterations=["Mohammed", "Muhammad"],
        ),
        age=Age(value=9, confidence="approximate"),
        relationship="son",
        last_seen=LastSeen(
            location="Aleppo, near the old market",
            date_text="three weeks before we left",
        ),
        guardian=Guardian(present=True, consent=True),
        distinguishing_marks=["scar above left eyebrow"],
    )

    payload = record.model_dump()
    rebuilt = RFLRecord.model_validate(payload)

    assert rebuilt == record


def test_rfl_record_accepts_partial_intake() -> None:
    """An RFLRecord with only `name` populated must validate and
    round-trip cleanly. Multi-turn intake builds records
    incrementally; partial states must be valid mid-flow.
    """
    record = RFLRecord(
        name=Name(canonical="Maria", source_script="latin"),
    )

    assert record.age is None
    assert record.relationship is None
    assert record.last_seen is None
    assert record.guardian is None
    assert record.distinguishing_marks == []

    payload = record.model_dump()
    rebuilt = RFLRecord.model_validate(payload)
    assert rebuilt == record


def test_name_source_script_rejects_invalid_literal() -> None:
    """Name.source_script is a Literal — non-member values must
    raise ValidationError. Regression guard against future changes
    that drop the Literal in favor of free-form str.
    """
    with pytest.raises(ValidationError):
        Name(canonical="Worf", source_script="klingon")  # type: ignore[arg-type]


# ─── B2-S9: FamilyMember + extended RFLRecord ───────────────────────


def test_family_member_defaults() -> None:
    """name and relationship_to_searcher are required; all other fields
    apply defaults. status defaults to 'missing'; age, last_seen_location,
    name_transliteration default to None.
    """
    member = FamilyMember(name="Mariam", relationship_to_searcher="sister")

    assert member.name == "Mariam"
    assert member.relationship_to_searcher == "sister"
    assert member.status == "missing"
    assert member.age is None
    assert member.last_seen_location is None
    assert member.name_transliteration is None


def test_family_member_status_rejects_invalid_literal() -> None:
    """FamilyMember.status is a Literal — non-member values raise
    ValidationError. Guards against extraction layer passing arbitrary
    strings from the model.
    """
    with pytest.raises(ValidationError):
        FamilyMember(
            name="Yusuf",
            relationship_to_searcher="brother",
            status="deceased",  # type: ignore[arg-type]
        )


def test_rfl_record_with_family_roster_round_trips() -> None:
    """RFLRecord with a populated family_roster round-trips through
    model_dump / model_validate with all member fields preserved.
    Covers the two-member case with mixed statuses.
    """
    record = RFLRecord(
        name=Name(canonical="يوسف", source_script="arabic"),
        family_roster=[
            FamilyMember(
                name="مريم",
                name_transliteration="Mariam",
                relationship_to_searcher="sister",
                status="missing",
                age=32,
                last_seen_location="southern gate",
            ),
            FamilyMember(
                name="محمد",
                relationship_to_searcher="nephew",
                status="missing",
            ),
        ],
    )

    payload = record.model_dump()
    rebuilt = RFLRecord.model_validate(payload)

    assert rebuilt == record
    assert len(rebuilt.family_roster) == 2
    assert rebuilt.family_roster[0].name_transliteration == "Mariam"
    assert rebuilt.family_roster[1].age is None


def test_rfl_record_with_searcher_fields_round_trips() -> None:
    """RFLRecord with searcher_name and searcher_relationship_to_target
    populated round-trips cleanly. Legacy relationship field coexists
    without conflict.
    """
    record = RFLRecord(
        name=Name(canonical="Mohamad", source_script="latin"),
        relationship="uncle",
        searcher_name="يوسف",
        searcher_name_transliteration="Yusuf",
        searcher_relationship_to_target="uncle",
    )

    payload = record.model_dump()
    rebuilt = RFLRecord.model_validate(payload)

    assert rebuilt == record
    assert rebuilt.relationship == "uncle"
    assert rebuilt.searcher_name == "يوسف"
    assert rebuilt.searcher_name_transliteration == "Yusuf"
    assert rebuilt.searcher_relationship_to_target == "uncle"
    assert rebuilt.family_roster == []
