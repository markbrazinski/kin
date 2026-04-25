"""Structural tests for RFLRecord and its sub-models (Day 6 Session 3).

Three tests prove the schema's structural invariants. Field-semantic
tests (e.g., "transliterations should not be empty for arabic
source_script") are matching-layer concerns and live elsewhere.
"""

import pytest
from pydantic import ValidationError

from core.rfl_schema import (
    Age,
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
