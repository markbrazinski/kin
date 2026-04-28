"""Structural tests for IntakeRecord, MatchLink, AuditEvent.

Pure schema behavior — no I/O, no storage adapter. Proves
required-field enforcement, Literal enum validation, and round-trip
fidelity through model_dump_json / model_validate_json (the
serialization path the storage adapter relies on).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
