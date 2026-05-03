"""Tests for fixture_seed.py (S17).

Validates that seeded fixture records have correct schema, status,
audit history shape, timestamp staggering, and that match scoring
across Yusuf + Mariam produces expected NodeMatches.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from core.matching import match_records_network
from core.rfl_schema import FamilyMember, Name, RFLRecord, Age
from integration.fixture_seed import (
    MARIAM_ID,
    YUSUF_ID,
    seed_all,
    seed_mariam,
    seed_yusuf,
)
from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import _to_rfl_record
from tests.fakes.fake_clock import FakeClock


def _adapter(tmp_path: Path) -> StorageAdapter:
    return StorageAdapter(tmp_path / "storage", FakeClock())


# ─── 1. Yusuf fixture schema and status ───────────────────────────────────────


def test_seed_yusuf_status_and_fields(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    record = seed_yusuf(storage)

    assert record.id == YUSUF_ID
    assert record.status == "paused_for_crisis"
    assert record.is_crisis is True
    assert record.language == "ar"
    assert record.searcher_name != ""
    assert record.full_name_source_script != ""
    assert record.referral_organization is not None
    # At least one family roster member (Mohamad) must be present.
    assert len(record.family_roster) >= 1
    mohamad = next(
        (m for m in record.family_roster if m.status == "missing"), None
    )
    assert mohamad is not None
    assert mohamad.age == 8


# ─── 2. Mariam fixture schema and status ─────────────────────────────────────


def test_seed_mariam_status_and_fields(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    record = seed_mariam(storage)

    assert record.id == MARIAM_ID
    assert record.status == "complete"
    assert record.is_crisis is False
    assert record.language == "ar"
    assert record.searcher_name != ""
    assert record.full_name_source_script != ""
    assert record.relationship_to_seeker != ""
    # Mohamad must be in family roster.
    assert len(record.family_roster) >= 1


# ─── 3. Match scoring produces NodeMatches across Yusuf + Mariam ─────────────


def test_match_scoring_yusuf_mariam_produces_node_matches(tmp_path: Path) -> None:
    """S13-rev: Yusuf is paused_for_crisis but his fields are preserved
    and participate in match scoring. Mariam's commit should produce at
    least one NodeMatch (Mohamad-pair as primary).
    """
    storage = _adapter(tmp_path)
    seed_all(storage)

    yusuf = storage.read_intake_record(YUSUF_ID)
    mariam = storage.read_intake_record(MARIAM_ID)
    assert yusuf is not None
    assert mariam is not None

    yusuf_rfl = _to_rfl_record(yusuf)
    mariam_rfl = _to_rfl_record(mariam)

    result = match_records_network(mariam_rfl, yusuf_rfl)

    assert result.matched is True
    assert result.primary_match is not None
    # Mohamad-pair primary composite score must be ≥ 0.70 (COMPOSITE_THRESHOLD).
    assert result.primary_match.composite_score >= 0.70


# ─── 4. Yusuf audit history has crisis_detected event ────────────────────────


def test_seed_yusuf_audit_has_crisis_detected(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    seed_yusuf(storage)

    crisis_events = storage.list_audit_events(event_type="crisis_detected")
    yusuf_crisis = [e for e in crisis_events if YUSUF_ID in e.record_ids]
    assert len(yusuf_crisis) >= 1


# ─── 5. Audit timestamps are staggered realistically ─────────────────────────


def test_seed_yusuf_audit_timestamps_staggered(tmp_path: Path) -> None:
    """Distinct update_intake_record call groups must produce different
    timestamps. Events within a single bulk call share one timestamp
    (same clock.now() tick), but consecutive call groups must differ.

    Strategy: collect the unique timestamps from field_extracted events
    and verify at least 3 distinct values exist (Yusuf has 4 bulk update
    calls before the crisis transition, so at least 3 distinct timestamps
    must be present among field_extracted events).
    """
    storage = _adapter(tmp_path)
    seed_yusuf(storage)

    field_events = [
        e
        for e in storage.list_audit_events(event_type="field_extracted")
        if YUSUF_ID in e.record_ids
    ]
    assert len(field_events) >= 2

    unique_timestamps = {e.at for e in field_events}
    assert len(unique_timestamps) >= 3, (
        f"Expected ≥3 distinct timestamps across field_extracted events, "
        f"got {len(unique_timestamps)}: {sorted(unique_timestamps)}"
    )


# ─── 6. Seed is idempotent ────────────────────────────────────────────────────


def test_seed_yusuf_idempotent(tmp_path: Path) -> None:
    """Calling seed_yusuf twice must not create duplicate records."""
    storage = _adapter(tmp_path)
    seed_yusuf(storage)
    seed_yusuf(storage)

    all_records = storage.list_intake_records()
    yusuf_records = [r for r in all_records if r.id == YUSUF_ID]
    assert len(yusuf_records) == 1


# ─── 7. field_extracted events carry source_utterance (S15a) ─────────────────


def test_seed_yusuf_field_extracted_carries_utterance(tmp_path: Path) -> None:
    """S15a: field_extracted events from the extraction phase (searcher_name,
    full_name_source_script, family_roster, etc.) must include source_utterance
    and whisper_translation. Crisis-transition events (is_crisis, referral_*)
    are status-management updates and intentionally omit utterance fields.
    """
    storage = _adapter(tmp_path)
    seed_yusuf(storage)

    # Extraction-phase fields — those emitted by the update calls that
    # pass source_utterance/whisper_translation in the seed.
    extraction_fields = {
        "searcher_name", "searcher_name_transliteration",
        "full_name_source_script", "full_name_transliteration",
        "relationship_to_seeker", "family_roster",
    }

    extraction_events = [
        e
        for e in storage.list_audit_events(event_type="field_extracted")
        if YUSUF_ID in e.record_ids
        and e.details.get("field_name") in extraction_fields
    ]
    assert len(extraction_events) >= 2, (
        f"Expected ≥2 extraction-phase field_extracted events, "
        f"got {len(extraction_events)}"
    )

    for event in extraction_events:
        assert "source_utterance" in event.details, (
            f"field_extracted for {event.details.get('field_name')!r} "
            f"missing source_utterance"
        )
        assert "whisper_translation" in event.details, (
            f"field_extracted for {event.details.get('field_name')!r} "
            f"missing whisper_translation"
        )
