"""Integration tests for StorageAdapter — JSONL CRUD + audit-event auto-emit.

Each test uses tmp_path for the storage directory and FakeClock for
deterministic timestamps. No mocks at the adapter level — real file I/O
in tmp.

Audit-event mapping coverage:
  intake_created           — test_create_intake_record_*
  intake_paused            — test_update_status_to_crisis_triple_emits
  crisis_detected          — test_update_status_to_crisis_triple_emits
  referral_issued          — test_update_status_to_crisis_triple_emits
  field_extracted          — test_update_intake_record_*field_extracted*
  match_proposed           — test_create_match_link_*
  match_confirmed          — test_update_match_link_status_to_confirmed*
  match_rejected           — test_update_match_link_status_to_rejected*
"""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from integration.storage_adapter import (
    AUDIT_FILE,
    INTAKE_FILE,
    MATCH_FILE,
    StorageAdapter,
)
from tests.fakes.fake_clock import FakeClock


def _adapter(tmp_path: Path) -> StorageAdapter:
    return StorageAdapter(tmp_path / "storage", FakeClock())


def test_storage_dir_created_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "deeply" / "nested" / "storage"
    assert not target.exists()
    StorageAdapter(target, FakeClock())
    assert target.is_dir()


def test_create_intake_record_persists_and_emits_intake_created(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(
        language="es",
        source_device_id="tent_a",
    )

    # Persisted to JSONL.
    intake_file = tmp_path / "storage" / INTAKE_FILE
    lines = intake_file.read_text().strip().splitlines()
    assert len(lines) == 1
    assert str(record.id) in lines[0]

    # Audit event emitted.
    events = adapter.list_audit_events()
    assert [e.event_type for e in events] == ["intake_created"]
    assert events[0].record_ids == [record.id]
    assert events[0].actor == "kin_system"


def test_read_intake_record_returns_none_for_missing_id(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    assert adapter.read_intake_record(uuid4()) is None


def test_list_intake_records_empty_when_no_writes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    assert adapter.list_intake_records() == []


def test_list_intake_records_returns_all(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    a = adapter.create_intake_record(language="es", source_device_id="tent_a")
    b = adapter.create_intake_record(language="ar", source_device_id="tent_b")
    all_records = adapter.list_intake_records()
    assert {r.id for r in all_records} == {a.id, b.id}


def test_update_intake_record_changes_field_and_emits_field_extracted(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(
        language="es",
        source_device_id="tent_a",
    )
    updated = adapter.update_intake_record(
        record.id,
        full_name_source_script="Carlos",
    )
    assert updated.full_name_source_script == "Carlos"

    # Round-trip via re-read.
    re_read = adapter.read_intake_record(record.id)
    assert re_read is not None
    assert re_read.full_name_source_script == "Carlos"

    # field_extracted emitted exactly once.
    events = adapter.list_audit_events(event_type="field_extracted")
    assert len(events) == 1
    assert events[0].details == {
        "field_name": "full_name_source_script",
        "value": "Carlos",
    }


def test_update_intake_record_no_op_emits_no_field_extracted(
    tmp_path: Path,
) -> None:
    """Same value as already-stored should NOT emit field_extracted."""
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(
        language="es",
        source_device_id="tent_a",
        full_name_source_script="Carlos",
    )
    adapter.update_intake_record(
        record.id,
        full_name_source_script="Carlos",  # unchanged
    )
    events = adapter.list_audit_events(event_type="field_extracted")
    assert events == []


def test_update_intake_record_status_to_paused_for_crisis_triple_emits(
    tmp_path: Path,
) -> None:
    """Status transition fires intake_paused → crisis_detected → referral_issued
    in that order, before any field_extracted on the same call.
    """
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(
        language="ar",
        source_device_id="tent_b",
    )
    # Sanity: only intake_created so far.
    pre = [e.event_type for e in adapter.list_audit_events()]
    assert pre == ["intake_created"]

    adapter.update_intake_record(
        record.id,
        status="paused_for_crisis",
        is_crisis=True,
        referral_issued=True,
        referral_organization="ICRC Family Links Network",
    )

    all_events = [e.event_type for e in adapter.list_audit_events()]
    # intake_created + the triple + field_extracted per non-status field.
    # Triple comes immediately after intake_created.
    assert all_events[0:4] == [
        "intake_created",
        "intake_paused",
        "crisis_detected",
        "referral_issued",
    ]
    # The remaining events are field_extracted (one per non-status changed field).
    remaining = all_events[4:]
    assert all(et == "field_extracted" for et in remaining)
    # Three non-status fields changed: is_crisis, referral_issued,
    # referral_organization.
    assert len(remaining) == 3


def test_update_intake_record_multiple_fields_emits_one_field_extracted_each(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(
        language="es",
        source_device_id="tent_a",
    )
    adapter.update_intake_record(
        record.id,
        full_name_source_script="Carlos",
        relationship_to_seeker="hijo",
        age=8,
    )
    events = adapter.list_audit_events(event_type="field_extracted")
    field_names = {e.details["field_name"] for e in events}
    assert field_names == {
        "full_name_source_script",
        "relationship_to_seeker",
        "age",
    }
    assert len(events) == 3


def test_update_intake_record_raises_keyerror_for_unknown_id(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    with pytest.raises(KeyError):
        adapter.update_intake_record(uuid4(), age=8)


def test_create_match_link_persists_and_emits_match_proposed(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record_a = adapter.create_intake_record(language="ar", source_device_id="tent_a")
    record_b = adapter.create_intake_record(language="ar", source_device_id="tent_b")

    link = adapter.create_match_link(
        record_a_id=record_a.id,
        record_b_id=record_b.id,
        confidence_band="high",
        confidence_score=0.91,
        match_reasoning={
            "matched_fields": ["name", "age"],
            "phonetic_score": 1.0,
            "reason": "same-script-exact",
        },
    )
    assert link.verification_status == "proposed"
    assert link.proposed_by == "kin_matching_v1"

    # Persisted.
    match_file = tmp_path / "storage" / MATCH_FILE
    assert str(link.id) in match_file.read_text()

    # Audit event emitted with candidate_count from caller (default 1).
    proposed = adapter.list_audit_events(event_type="match_proposed")
    assert len(proposed) == 1
    assert proposed[0].match_id == link.id
    assert set(proposed[0].record_ids) == {record_a.id, record_b.id}
    assert proposed[0].candidate_count == 1


def test_create_match_link_propagates_candidate_count_to_audit_event(
    tmp_path: Path,
) -> None:
    """Bundle 1.5 S5: candidate_count parameter rides through to the
    audit event so frontend matchCandidates state can derive the
    queue rail badge value without re-counting events."""
    adapter = _adapter(tmp_path)
    record_a = adapter.create_intake_record(language="ar", source_device_id="tent_a")
    record_b = adapter.create_intake_record(language="ar", source_device_id="tent_b")

    adapter.create_match_link(
        record_a_id=record_a.id,
        record_b_id=record_b.id,
        confidence_band="high",
        confidence_score=0.91,
        match_reasoning={"matched_fields": ["name"], "phonetic_score": 1.0, "reason": "x"},
        candidate_count=4,
    )
    proposed = adapter.list_audit_events(event_type="match_proposed")
    assert proposed[-1].candidate_count == 4


def test_emit_match_proposed_empty_writes_summary_event(
    tmp_path: Path,
) -> None:
    """Bundle 1.5 S5: empty-result match runs emit a summary event
    with record_ids=[new_record_id] and candidate_count=0 so the
    frontend can confirm "this turn produced no candidates" rather
    than guessing from event absence."""
    adapter = _adapter(tmp_path)
    record = adapter.create_intake_record(language="ar", source_device_id="tent_a")

    event = adapter.emit_match_proposed_empty(new_record_id=record.id)

    assert event.event_type == "match_proposed"
    assert event.record_ids == [record.id]
    assert event.candidate_count == 0
    assert event.match_id is None

    # Persisted to JSONL audit log.
    proposed = adapter.list_audit_events(event_type="match_proposed")
    assert len(proposed) == 1
    assert proposed[0].id == event.id


def test_update_match_link_status_to_confirmed_emits_match_confirmed(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record_a = adapter.create_intake_record(language="ar", source_device_id="tent_a")
    record_b = adapter.create_intake_record(language="ar", source_device_id="tent_b")
    link = adapter.create_match_link(
        record_a_id=record_a.id,
        record_b_id=record_b.id,
        confidence_band="high",
        confidence_score=0.91,
        match_reasoning={},
    )

    confirmed = adapter.update_match_link_status(
        link.id,
        "confirmed",
        verified_by="caseworker_alice",
    )
    assert confirmed.verification_status == "confirmed"
    assert confirmed.verified_by == "caseworker_alice"
    assert confirmed.verified_at is not None

    events = adapter.list_audit_events(event_type="match_confirmed")
    assert len(events) == 1
    assert events[0].match_id == link.id


def test_update_match_link_status_to_rejected_emits_match_rejected(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    record_a = adapter.create_intake_record(language="ar", source_device_id="tent_a")
    record_b = adapter.create_intake_record(language="ar", source_device_id="tent_b")
    link = adapter.create_match_link(
        record_a_id=record_a.id,
        record_b_id=record_b.id,
        confidence_band="medium",
        confidence_score=0.72,
        match_reasoning={},
    )

    adapter.update_match_link_status(link.id, "rejected", verified_by="caseworker_bob")

    events = adapter.list_audit_events(event_type="match_rejected")
    assert len(events) == 1
    assert events[0].match_id == link.id


def test_list_match_links_filters_by_record_id(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    a = adapter.create_intake_record(language="ar", source_device_id="tent_a")
    b = adapter.create_intake_record(language="ar", source_device_id="tent_b")
    c = adapter.create_intake_record(language="ar", source_device_id="tent_c")

    link_ab = adapter.create_match_link(
        record_a_id=a.id, record_b_id=b.id,
        confidence_band="high", confidence_score=0.9,
        match_reasoning={},
    )
    link_bc = adapter.create_match_link(
        record_a_id=b.id, record_b_id=c.id,
        confidence_band="medium", confidence_score=0.75,
        match_reasoning={},
    )

    a_links = adapter.list_match_links(record_id=a.id)
    assert {link.id for link in a_links} == {link_ab.id}

    b_links = adapter.list_match_links(record_id=b.id)
    assert {link.id for link in b_links} == {link_ab.id, link_bc.id}


def test_audit_events_jsonl_round_trips_via_list(tmp_path: Path) -> None:
    """Read the audit log file directly and confirm list_audit_events
    matches what's on disk.
    """
    adapter = _adapter(tmp_path)
    adapter.create_intake_record(language="es", source_device_id="tent_a")

    audit_file = tmp_path / "storage" / AUDIT_FILE
    raw_lines = audit_file.read_text().strip().splitlines()
    assert len(raw_lines) == 1

    events = adapter.list_audit_events()
    assert len(events) == 1
    # Round-trip through Pydantic produced the same id as what's on disk.
    assert str(events[0].id) in raw_lines[0]
