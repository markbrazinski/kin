"""Demo fixture seeding — deterministic records for rehearsal corpus.

Produces four IntakeRecords with staggered audit timestamps that read
as captured-live: Yusuf (paused_for_crisis), Mariam (complete), and
two ambient queue records (Spanish, Farsi). Canonical seed logic; CLI
wrapper lives at scripts/seed_demo_fixtures.py; DemoDock POST handler
lives in src/ui/server/routes/demo.py.

Design notes:
- Fixed UUID constants so PRESENTATION_INITIAL_QUEUE_IDS can reference
  exact record IDs deterministically.
- Uses FakeClock with advance_now() to produce realistic intra-session
  timestamp spreads (intake_created at T+0, field_extracted events
  staggered 3-8s apart, crisis/complete events at ~22-25s).
- Idempotent: if a record with the fixture UUID already exists, it is
  deleted and recreated so each seed call produces a clean state.
- Calls storage.update_intake_record() once per field to emit one
  field_extracted audit event per field — same audit shape as a live
  intake. source_utterance and whisper_translation are provided so the
  S15 audit panel can surface "Source Arabic / Whisper translation /
  Gemma extraction" sub-blocks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from core.rfl_schema import FamilyMember
from core.storage_schemas import IntakeRecord
from integration.storage_adapter import StorageAdapter
from tests.fakes.fake_clock import FakeClock

# ─── Deterministic fixture UUIDs ─────────────────────────────────────────────

YUSUF_ID = UUID("00000000-0000-0000-0000-000000000042")
MARIAM_ID = UUID("00000000-0000-0000-0000-000000000049")
AMBIENT_A_ID = UUID("00000000-0000-0000-0000-000000000089")
AMBIENT_B_ID = UUID("00000000-0000-0000-0000-000000000102")

# String forms for PRESENTATION_INITIAL_QUEUE_IDS and frontend checks
YUSUF_ID_STR = str(YUSUF_ID)
MARIAM_ID_STR = str(MARIAM_ID)
AMBIENT_A_ID_STR = str(AMBIENT_A_ID)
AMBIENT_B_ID_STR = str(AMBIENT_B_ID)

# Base timestamp: realistic demo-day time
_SEED_BASE = datetime(2026, 5, 5, 9, 30, 0, tzinfo=timezone.utc)


def _remove_fixture(storage: StorageAdapter, fixture_id: UUID) -> None:
    """Delete existing fixture record from JSONL by rewriting without it."""
    records = storage.list_intake_records()
    filtered = [r for r in records if r.id != fixture_id]
    if len(filtered) < len(records):
        from pathlib import Path
        intake_path = storage._dir / "intake_records.jsonl"
        storage._rewrite_jsonl(intake_path, filtered)
        # Also prune audit events for this record.
        audit_path = storage._dir / "audit_events.jsonl"
        events = storage.list_audit_events()
        kept = [e for e in events if fixture_id not in e.record_ids]
        storage._rewrite_jsonl(audit_path, kept)


def _make_clock(base_offset_s: float = 0.0) -> FakeClock:
    """Clock starting at _SEED_BASE + base_offset_s."""
    start = _SEED_BASE
    from datetime import timedelta
    clock: FakeClock = FakeClock(start_now=start + timedelta(seconds=base_offset_s))
    return clock


# ─── Yusuf — Arabic, paused_for_crisis ───────────────────────────────────────

# Yusuf's source utterance (Arabic, as Whisper would transcribe)
_YUSUF_SOURCE = (
    "أنا يوسف العمر. أبحث عن زوجتي مريم وابني محمد عمره ٨ سنوات. "
    "كانت أختي عائشة معنا لكنها الآن في مخيم ثاني. ما عاد فيني أكمل."
)
_YUSUF_TRANSLATION = (
    "I am Yusuf Al-Omar. I am looking for my wife Mariam and my son Mohamad, "
    "aged 8. My sister Aisha was with us but is now in another camp. "
    "I can't go on."
)


def seed_yusuf(storage: StorageAdapter) -> IntakeRecord:
    """Seed Yusuf's paused_for_crisis record with realistic audit history."""
    _remove_fixture(storage, YUSUF_ID)

    clock = _make_clock(0.0)

    # Patch the storage clock so audit timestamps come from our fake.
    original_clock = storage._clock
    storage._clock = clock

    try:
        # T+0 — intake_created
        record = storage.create_intake_record(
            language="ar",
            source_device_id="demo_tent_a",
            status="partial",
        )
        # Overwrite the random UUID with our deterministic fixture ID.
        record = _replace_id(storage, record, YUSUF_ID)

        # T+3s — searcher_name
        clock.advance_now(3)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_YUSUF_SOURCE,
            whisper_translation=_YUSUF_TRANSLATION,
            searcher_name="يوسف العمر",
            searcher_name_transliteration="Yusuf Al-Omar",
        )

        # T+8s — missing_persons (Mariam)
        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_YUSUF_SOURCE,
            whisper_translation=_YUSUF_TRANSLATION,
            full_name_source_script="مريم العمر",
            full_name_transliteration="Mariam Al-Omar",
            relationship_to_seeker="زوجة",
        )

        # T+13s — missing_persons (Mohamad)
        clock.advance_now(5)
        mohamad = FamilyMember(
            name="محمد",
            name_transliteration="Mohamad",
            relationship_to_searcher="ابن",
            status="missing",
            age=8,
        )
        record = storage.update_intake_record(
            record.id,
            source_utterance=_YUSUF_SOURCE,
            whisper_translation=_YUSUF_TRANSLATION,
            family_roster=[mohamad],
        )

        # T+17s — roster member (Aisha, present)
        clock.advance_now(4)
        aisha = FamilyMember(
            name="عائشة",
            name_transliteration="Aisha",
            relationship_to_searcher="أخت",
            status="present",
        )
        record = storage.update_intake_record(
            record.id,
            source_utterance=_YUSUF_SOURCE,
            whisper_translation=_YUSUF_TRANSLATION,
            family_roster=[mohamad, aisha],
        )

        # T+22s — crisis detected → paused_for_crisis (triple-emit)
        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            status="paused_for_crisis",
            is_crisis=True,
            crisis_match_path="keyword",
            referral_issued=True,
            referral_organization="ICRC Family Links Network",
        )

    finally:
        storage._clock = original_clock

    return record


# ─── Mariam — Arabic, complete ────────────────────────────────────────────────

_MARIAM_SOURCE = (
    "أنا مريم صالح. أبحث عن زوجي يوسف وابني محمد عمره ٨ سنوات. "
    "تفرقنا في الحدود قبل ثلاثة أيام."
)
_MARIAM_TRANSLATION = (
    "I am Mariam Saleh. I am looking for my husband Yusuf and my son Mohamad, "
    "aged 8. We were separated at the border three days ago."
)


def seed_mariam(storage: StorageAdapter) -> IntakeRecord:
    """Seed Mariam's complete record with realistic audit history."""
    _remove_fixture(storage, MARIAM_ID)

    clock = _make_clock(3600.0)  # 1 hour after Yusuf for demo realism

    original_clock = storage._clock
    storage._clock = clock

    try:
        # T+0 — intake_created
        record = storage.create_intake_record(
            language="ar",
            source_device_id="demo_tent_b",
            status="partial",
        )
        record = _replace_id(storage, record, MARIAM_ID)

        # T+3s — searcher_name
        clock.advance_now(3)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_MARIAM_SOURCE,
            whisper_translation=_MARIAM_TRANSLATION,
            searcher_name="مريم صالح",
            searcher_name_transliteration="Mariam Saleh",
        )

        # T+8s — primary missing person (Yusuf)
        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_MARIAM_SOURCE,
            whisper_translation=_MARIAM_TRANSLATION,
            full_name_source_script="يوسف",
            full_name_transliteration="Yusuf",
            relationship_to_seeker="زوج",
        )

        # T+13s — Mohamad (missing family member, minor)
        clock.advance_now(5)
        mohamad = FamilyMember(
            name="محمد",
            name_transliteration="Mohamad",
            relationship_to_searcher="ابن",
            status="missing",
            age=8,
        )
        record = storage.update_intake_record(
            record.id,
            source_utterance=_MARIAM_SOURCE,
            whisper_translation=_MARIAM_TRANSLATION,
            family_roster=[mohamad],
            is_minor=False,
        )

        # T+17s — location + date
        clock.advance_now(4)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_MARIAM_SOURCE,
            whisper_translation=_MARIAM_TRANSLATION,
            last_seen_location="الحدود السورية اللبنانية",
            last_seen_date="3 days ago",
        )

        # T+22s — promote to complete
        clock.advance_now(5)
        record = storage.update_intake_record(record.id, status="complete")

    finally:
        storage._clock = original_clock

    return record


# ─── Ambient A — Spanish, complete ───────────────────────────────────────────

_AMBIENT_A_SOURCE = (
    "Estoy buscando a mi madre Carmen Reyes. Nos separamos en la frontera "
    "con México hace cinco días. Tiene 58 años."
)
_AMBIENT_A_TRANSLATION = (
    "I am looking for my mother Carmen Reyes. We were separated at the "
    "Mexico border five days ago. She is 58 years old."
)


def seed_ambient_a(storage: StorageAdapter) -> IntakeRecord:
    """Seed ambient queue record A — Spanish, complete."""
    _remove_fixture(storage, AMBIENT_A_ID)

    clock = _make_clock(7200.0)  # 2 hours after Yusuf

    original_clock = storage._clock
    storage._clock = clock

    try:
        record = storage.create_intake_record(
            language="es",
            source_device_id="demo_tent_c",
            status="partial",
        )
        record = _replace_id(storage, record, AMBIENT_A_ID)

        clock.advance_now(3)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_AMBIENT_A_SOURCE,
            whisper_translation=_AMBIENT_A_TRANSLATION,
            full_name_source_script="Carmen Reyes",
            full_name_transliteration="Carmen Reyes",
        )

        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_AMBIENT_A_SOURCE,
            whisper_translation=_AMBIENT_A_TRANSLATION,
            relationship_to_seeker="madre",
            age=58,
        )

        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_AMBIENT_A_SOURCE,
            whisper_translation=_AMBIENT_A_TRANSLATION,
            last_seen_location="Frontera México–Guatemala",
            last_seen_date="5 days ago",
        )

        clock.advance_now(5)
        record = storage.update_intake_record(record.id, status="complete")

    finally:
        storage._clock = original_clock

    return record


# ─── Ambient B — Farsi, partial ──────────────────────────────────────────────

_AMBIENT_B_SOURCE = (
    "من دنبال برادرم رضا می‌گردم. پنج روز پیش از هم جدا شدیم "
    "در کمپ مرزی. او ۳۲ سال دارد."
)
_AMBIENT_B_TRANSLATION = (
    "I am looking for my brother Reza. We were separated five days ago "
    "at the border camp. He is 32 years old."
)


def seed_ambient_b(storage: StorageAdapter) -> IntakeRecord:
    """Seed ambient queue record B — Farsi, partial."""
    _remove_fixture(storage, AMBIENT_B_ID)

    clock = _make_clock(10800.0)  # 3 hours after Yusuf

    original_clock = storage._clock
    storage._clock = clock

    try:
        record = storage.create_intake_record(
            language="fa",
            source_device_id="demo_tent_d",
            status="partial",
        )
        record = _replace_id(storage, record, AMBIENT_B_ID)

        clock.advance_now(3)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_AMBIENT_B_SOURCE,
            whisper_translation=_AMBIENT_B_TRANSLATION,
            full_name_source_script="رضا",
            full_name_transliteration="Reza",
        )

        clock.advance_now(5)
        record = storage.update_intake_record(
            record.id,
            source_utterance=_AMBIENT_B_SOURCE,
            whisper_translation=_AMBIENT_B_TRANSLATION,
            relationship_to_seeker="برادر",
            age=32,
        )

        # Deliberately partial — no location yet; shows queue status diversity.

    finally:
        storage._clock = original_clock

    return record


# ─── Seed all ────────────────────────────────────────────────────────────────


def seed_all(storage: StorageAdapter) -> dict[str, IntakeRecord]:
    """Seed all four fixture records. Returns {name: record} mapping."""
    return {
        "yusuf": seed_yusuf(storage),
        "mariam": seed_mariam(storage),
        "ambient_a": seed_ambient_a(storage),
        "ambient_b": seed_ambient_b(storage),
    }


# ─── ID replacement helper ────────────────────────────────────────────────────


def _replace_id(
    storage: StorageAdapter,
    record: IntakeRecord,
    new_id: UUID,
) -> IntakeRecord:
    """Swap record.id to a deterministic fixture UUID in-place in JSONL.

    JSONL rewrite: read all records, replace the random UUID on the target
    record, rewrite. Also patches audit events that reference the old ID.
    Not safe for concurrent use; seed is CLI/dev-only.
    """
    old_id = record.id

    # Rewrite intake records with patched ID.
    records = storage.list_intake_records()
    patched: list[IntakeRecord] = []
    for r in records:
        if r.id == old_id:
            patched.append(r.model_copy(update={"id": new_id}))
        else:
            patched.append(r)
    storage._rewrite_jsonl(storage._dir / "intake_records.jsonl", patched)

    # Rewrite audit events that reference old_id.
    events = storage.list_audit_events()
    patched_events = []
    for e in events:
        new_record_ids = [new_id if r == old_id else r for r in e.record_ids]
        if new_record_ids != list(e.record_ids):
            patched_events.append(e.model_copy(update={"record_ids": new_record_ids}))
        else:
            patched_events.append(e)
    storage._rewrite_jsonl(storage._dir / "audit_events.jsonl", patched_events)

    return record.model_copy(update={"id": new_id})
