"""Structural tests for IntakeRecord, MatchLink, AuditEvent.

Pure schema behavior — no I/O, no storage adapter. Proves
required-field enforcement, Literal enum validation, and round-trip
fidelity through model_dump_json / model_validate_json (the
serialization path the storage adapter relies on).

B2-S9 additions: three tests for the extended IntakeRecord fields
(family_roster, searcher_*) and backward-compat default behavior.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.rfl_schema import FamilyMember
from core.storage_schemas import (
    AuditEvent,
    IntakeRecord,
    MatchLink,
)

_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


def test_intake_record_round_trips_full_payload() -> None:
    """A fully-populated IntakeRecord round-trips through JSON without loss."""
    record = IntakeRecord(
        id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        status="complete",
        language="ar",
        source_device_id="tent_a",
        full_name_source_script="محمد",
        full_name_transliteration="Mohammed",
        relationship_to_seeker="son",
        age=8,
        last_seen_location="مخيم الزعتري",
        last_seen_date="hace dos semanas",
        distinguishing_marks="scar above left eyebrow",
        is_minor=True,
        is_crisis=False,
        crisis_match_path=None,
        referral_issued=False,
        referral_organization=None,
    )
    rt = IntakeRecord.model_validate_json(record.model_dump_json())
    assert rt == record


def test_intake_record_minimum_fields_applies_defaults() -> None:
    """Only required fields populated; defaults fill the rest cleanly."""
    record = IntakeRecord(
        id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        status="partial",
        language="es",
        source_device_id="tent_b",
    )
    assert record.full_name_source_script == ""
    assert record.full_name_transliteration == ""
    assert record.relationship_to_seeker == ""
    assert record.age is None
    assert record.is_minor is False
    assert record.is_crisis is False
    assert record.crisis_match_path is None
    assert record.referral_issued is False
    assert record.referral_organization is None


def test_intake_record_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        IntakeRecord(
            id=uuid4(),
            created_at=_NOW,
            updated_at=_NOW,
            status="archived",  # not a valid IntakeStatus
            language="es",
            source_device_id="tent_a",
        )


def test_match_link_round_trips_with_match_reasoning_dict() -> None:
    link = MatchLink(
        id=uuid4(),
        record_a_id=uuid4(),
        record_b_id=uuid4(),
        confidence_band="high",
        confidence_score=0.92,
        verification_status="proposed",
        proposed_at=_NOW,
        proposed_by="kin_matching_v1",
        match_reasoning={
            "matched_fields": ["name", "age"],
            "phonetic_score": 1.0,
            "reason": "same-script-exact + age match",
        },
    )
    rt = MatchLink.model_validate_json(link.model_dump_json())
    assert rt == link
    assert rt.match_reasoning["matched_fields"] == ["name", "age"]


def test_match_link_rejects_invalid_confidence_band() -> None:
    with pytest.raises(ValidationError):
        MatchLink(
            id=uuid4(),
            record_a_id=uuid4(),
            record_b_id=uuid4(),
            confidence_band="certain",  # not high/medium/low
            confidence_score=0.99,
            verification_status="proposed",
            proposed_at=_NOW,
            proposed_by="kin_matching_v1",
            match_reasoning={},
        )


def test_audit_event_accepts_all_event_types() -> None:
    """Every AuditEventType in the enum constructs cleanly."""
    event_types = [
        "intake_created",
        "intake_paused",
        "crisis_detected",
        "referral_issued",
        "match_proposed",
        "match_confirmed",
        "match_rejected",
        "field_extracted",
    ]
    for et in event_types:
        event = AuditEvent(
            id=uuid4(),
            at=_NOW,
            event_type=et,  # type: ignore[arg-type]
            record_ids=[uuid4()],
        )
        rt = AuditEvent.model_validate_json(event.model_dump_json())
        assert rt.event_type == et


def test_audit_event_rejects_invalid_event_type() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            id=uuid4(),
            at=_NOW,
            event_type="minor_flagged",  # structlog-only, not a persisted type
        )


# ─── B2-S9: extended IntakeRecord fields ────────────────────────────


def test_intake_record_empty_roster_default() -> None:
    """Minimal IntakeRecord (pre-S9 shape) applies empty-list and
    empty-string defaults for all new S9 fields. Proves backward
    compat: existing JSONL records without these keys load cleanly.
    """
    record = IntakeRecord(
        id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        status="partial",
        language="ar",
        source_device_id="tent_a",
    )

    assert record.family_roster == []
    assert record.searcher_name == ""
    assert record.searcher_name_transliteration == ""
    assert record.searcher_relationship_to_target == ""


def test_intake_record_with_family_roster_round_trips() -> None:
    """IntakeRecord with a populated family_roster round-trips through
    model_dump_json / model_validate_json with all nested fields
    preserved. This is the storage adapter's exact serialization path.
    """
    roster = [
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
    ]
    record = IntakeRecord(
        id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        status="partial",
        language="ar",
        source_device_id="tent_a",
        full_name_source_script="يوسف",
        full_name_transliteration="Yusuf",
        family_roster=roster,
    )

    rt = IntakeRecord.model_validate_json(record.model_dump_json())

    assert rt == record
    assert len(rt.family_roster) == 2
    assert rt.family_roster[0].name_transliteration == "Mariam"
    assert rt.family_roster[0].age == 32
    assert rt.family_roster[1].last_seen_location is None


def test_intake_record_with_searcher_fields_round_trips() -> None:
    """IntakeRecord with searcher_name and searcher_relationship_to_target
    populated round-trips cleanly through JSON serialization.
    """
    record = IntakeRecord(
        id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        status="partial",
        language="fa",
        source_device_id="tent_b",
        searcher_name="یوسف",
        searcher_name_transliteration="Yusuf",
        searcher_relationship_to_target="uncle",
    )

    rt = IntakeRecord.model_validate_json(record.model_dump_json())

    assert rt == record
    assert rt.searcher_name == "یوسف"
    assert rt.searcher_name_transliteration == "Yusuf"
    assert rt.searcher_relationship_to_target == "uncle"
