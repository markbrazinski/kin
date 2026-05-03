"""Trigger contract tests for _trigger_matching (S5 ITEM D + S13-rev).

Five tests covering the matching trigger contract:
  1. Trigger fires on creation, emits matching_trigger_fired even
     when no candidates exist.
  2. Trigger does NOT fire on read/list operations.
  3. paused_for_crisis records ARE included in the candidate pool (S13-rev).
  4. A paused_for_crisis record cannot itself trigger matching (fire
     direction: matching fires on the newly-committed record only).
  5. Multiple matching candidates each become a MatchLink row.

These tests call _trigger_matching directly (not via ingest_audio) to
keep the focus on the trigger contract. The ingest_audio integration
is exercised by tests/integration/test_ingest_audio.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import structlog

from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import _trigger_matching
from tests.fakes.fake_clock import FakeClock


def _adapter(tmp_path: Path) -> StorageAdapter:
    return StorageAdapter(tmp_path / "storage", FakeClock())


def _create_mohamad(
    storage: StorageAdapter,
    source_device_id: str,
    *,
    status: str = "complete",
):
    """Helper: create a populated 'محمد' Arabic IntakeRecord directly
    in storage (no audio pipeline, no extraction). Returns the record.

    All Mohamads are 8-year-old sons by design so any pair satisfies
    the matching gate + corroborating fields.
    """
    record = storage.create_intake_record(
        language="ar",
        source_device_id=source_device_id,
        status="partial",
    )
    return storage.update_intake_record(
        record.id,
        full_name_source_script="محمد",
        relationship_to_seeker="ابن",
        age=8,
        is_minor=True,
        status=status,
    )


# ─── 1. Trigger fires with no candidates ──────────────────────────


@pytest.mark.asyncio
async def test_trigger_fires_on_new_record_with_no_candidates(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    record = _create_mohamad(storage, "tent_a")

    with structlog.testing.capture_logs() as cap_logs:
        links = await _trigger_matching(record, storage=storage)

    assert links == []
    assert storage.list_match_links() == []

    trigger_events = [
        log for log in cap_logs if log["event"] == "matching_trigger_fired"
    ]
    assert len(trigger_events) == 1
    assert trigger_events[0]["candidate_count"] == 0
    assert trigger_events[0]["match_count"] == 0


# ─── 2. Trigger does NOT fire on read operations ──────────────────


@pytest.mark.asyncio
async def test_trigger_does_not_fire_on_read_operations(
    tmp_path: Path,
) -> None:
    """Reading records should never produce match_links or fire the
    trigger. This proves matching is gated to creation, not bound to
    read paths.
    """
    storage = _adapter(tmp_path)
    record_a = _create_mohamad(storage, "tent_a")
    record_b = _create_mohamad(storage, "tent_b")

    # Sanity: no trigger has fired yet (records were created via
    # storage directly, not via _trigger_matching).
    assert storage.list_match_links() == []

    with structlog.testing.capture_logs() as cap_logs:
        # Repeated reads.
        for _ in range(3):
            storage.list_intake_records()
            storage.read_intake_record(record_a.id)
            storage.read_intake_record(record_b.id)

    # Reads produced no MatchLinks and no trigger events.
    assert storage.list_match_links() == []
    trigger_events = [
        log for log in cap_logs if log["event"] == "matching_trigger_fired"
    ]
    assert trigger_events == []


# ─── 3. paused_for_crisis candidates ARE included (S13-rev) ───────


@pytest.mark.asyncio
async def test_trigger_includes_paused_for_crisis_candidates(
    tmp_path: Path,
) -> None:
    """S13-rev: a paused_for_crisis record matching the new record on
    identity fields SHOULD produce a MatchLink. The intake is paused
    but the data is not lost — extracted fields participate in match
    scoring identically to committed records.

    Also verifies includes_paused_candidates=True annotation fires on
    the match_proposed audit event when a paused record contributed.
    """
    storage = _adapter(tmp_path)
    # Paused-for-crisis Mohamad with preserved fields.
    _create_mohamad(storage, "tent_crisis", status="paused_for_crisis")
    # The new record we trigger matching on.
    new_record = _create_mohamad(storage, "tent_b")

    with structlog.testing.capture_logs() as cap_logs:
        links = await _trigger_matching(new_record, storage=storage)

    assert len(links) == 1
    assert links[0].record_a_id == new_record.id

    trigger_events = [
        log for log in cap_logs if log["event"] == "matching_trigger_fired"
    ]
    assert len(trigger_events) == 1
    assert trigger_events[0]["candidate_count"] == 1
    assert trigger_events[0]["match_count"] == 1

    # includes_paused_candidates annotation fires in the match_proposed event.
    proposed_events = storage.list_audit_events(event_type="match_proposed")
    assert len(proposed_events) == 1
    assert proposed_events[0].details.get("includes_paused_candidates") is True


# ─── 4. paused_for_crisis record cannot be the trigger origin ─────


@pytest.mark.asyncio
async def test_paused_record_does_not_itself_trigger_matching(
    tmp_path: Path,
) -> None:
    """A paused_for_crisis record should never appear as the new_record
    arg to _trigger_matching — matching fires on newly-committed records
    only. This test verifies the fire-direction contract: when a paused
    record is passed as new_record (which the pipeline never does, but
    which code must handle gracefully), it cannot self-match, and the
    non-paused candidate in storage does match it.

    Practical coverage: the pipeline's crisis path calls
    _persist_crisis_record which does NOT call _trigger_matching, so
    this scenario is defense-in-depth, not a production path.
    """
    storage = _adapter(tmp_path)
    # A committed Mohamad in storage (the candidate).
    committed = _create_mohamad(storage, "tent_committed")
    # A paused record as the "trigger origin" — atypical but must not crash.
    paused = _create_mohamad(storage, "tent_paused", status="paused_for_crisis")

    links = await _trigger_matching(paused, storage=storage)

    # committed Mohamad is a candidate; paused record self-match is excluded.
    assert len(links) == 1
    assert links[0].record_a_id == paused.id
    assert links[0].record_b_id == committed.id


# ─── 5. Multiple matching candidates → multiple MatchLinks ────────


@pytest.mark.asyncio
async def test_trigger_creates_one_match_link_per_matching_candidate(
    tmp_path: Path,
) -> None:
    """Three pre-existing 'محمد' candidates plus one new 'محمد' should
    produce exactly 3 MatchLinks (one per candidate). Each MatchLink
    should reference the new record as record_a_id and a distinct
    candidate as record_b_id. Audit log should contain exactly 3
    match_proposed events.
    """
    storage = _adapter(tmp_path)
    candidate_1 = _create_mohamad(storage, "tent_1")
    candidate_2 = _create_mohamad(storage, "tent_2")
    candidate_3 = _create_mohamad(storage, "tent_3")
    new_record = _create_mohamad(storage, "tent_new")

    links = await _trigger_matching(new_record, storage=storage)

    assert len(links) == 3
    candidate_ids = {candidate_1.id, candidate_2.id, candidate_3.id}
    for link in links:
        assert link.record_a_id == new_record.id
        assert link.record_b_id in candidate_ids
        assert link.verification_status == "proposed"
        assert link.confidence_band == "high"

    # Distinct candidates — no duplicate record_b_ids.
    assert len({link.record_b_id for link in links}) == 3

    # Three match_proposed audit events.
    proposed_events = storage.list_audit_events(event_type="match_proposed")
    assert len(proposed_events) == 3
