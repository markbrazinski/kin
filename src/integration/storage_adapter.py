"""Local JSONL queue for structured records; no network.

Persists IntakeRecord, MatchLink, AuditEvent to three JSONL files in a
storage directory. Owns the audit-event mapping: every CRUD operation
that should generate an audit_event auto-emits the corresponding event
as part of the same call. Pipeline never writes audit events directly.

Concurrency model: none. Single-writer assumption. Read-modify-write
on update_* methods rewrites the whole file. No fcntl, no atomic
write-then-rename. If concurrent writers ever land, that's a separate
brief.

Audit-event mapping (Part 1 REV 4 + Part 2 REV 3):

| Operation                                             | Event(s)         |
|-------------------------------------------------------|------------------|
| create_intake_record                                  | intake_created   |
| update_intake_record (status → paused_for_crisis)     | intake_paused +  |
|                                                       | crisis_detected +|
|                                                       | referral_issued  |
|                                                       | (in that order)  |
| update_intake_record (other field changed)            | one              |
|                                                       | field_extracted  |
|                                                       | per field        |
| create_match_link                                     | match_proposed   |
| update_match_link_status (→ confirmed)                | match_confirmed  |
| update_match_link_status (→ rejected)                 | match_rejected   |

Per-field field_extracted payload: details = {"field_name": <name>,
"value": <new value>}. No-op updates (value unchanged) emit nothing.

Time injection: takes a Clock for deterministic timestamps in tests.
Production code passes SYSTEM_CLOCK (system_clock.py); tests pass
FakeClock (tests/fakes/fake_clock.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

from pydantic import ValidationError

from core.clock import Clock
from core.storage_schemas import (
    AuditEvent,
    AuditEventType,
    ConfidenceBand,
    IntakeRecord,
    IntakeStatus,
    MatchLink,
    SupportedLanguage,
    VerificationStatus,
)

INTAKE_FILE = "intake_records.jsonl"
MATCH_FILE = "match_links.jsonl"
AUDIT_FILE = "audit_events.jsonl"


class StorageAdapter:
    """JSONL-backed CRUD with auto-emitted audit events.

    Constructor creates `storage_dir` if missing; the three JSONL files
    are created on first write (not in __init__). Reads from missing
    files return empty results.
    """

    def __init__(
        self,
        storage_dir: Path,
        clock: Clock,
        actor: str = "kin_system",
    ) -> None:
        self._dir = storage_dir
        self._clock = clock
        self._actor = actor
        self._dir.mkdir(parents=True, exist_ok=True)

    # ─── IntakeRecord CRUD ───────────────────────────────────────

    def create_intake_record(
        self,
        language: SupportedLanguage,
        source_device_id: str,
        status: IntakeStatus = "partial",
        **fields: Any,
    ) -> IntakeRecord:
        """Create + persist an IntakeRecord. Emits intake_created."""
        now = self._clock.now()
        record = IntakeRecord(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            status=status,
            language=language,
            source_device_id=source_device_id,
            **fields,
        )
        self._append_jsonl(self._dir / INTAKE_FILE, record)
        self._append_audit_event(
            event_type="intake_created",
            record_ids=[record.id],
        )
        return record

    def read_intake_record(self, id: UUID) -> IntakeRecord | None:
        for record in self._iter_intake_records():
            if record.id == id:
                return record
        return None

    def list_intake_records(self) -> list[IntakeRecord]:
        return list(self._iter_intake_records())

    def update_intake_record(
        self,
        id: UUID,
        *,
        source_utterance: str | None = None,
        whisper_translation: str | None = None,
        **fields: Any,
    ) -> IntakeRecord:
        """Read-modify-write. Emits field_extracted per changed field;
        triple-emits intake_paused + crisis_detected + referral_issued
        on status transition to paused_for_crisis.

        source_utterance and whisper_translation are optional metadata
        included in field_extracted event details when provided (S15a).
        They record which spoken utterance and Whisper translation
        produced the extracted fields, enabling the audit panel to show
        "Source Arabic / Whisper translation / Gemma extraction" per
        NodeMatch. Not stored on the IntakeRecord itself — audit-only.
        """
        records = self.list_intake_records()
        idx = next(
            (i for i, r in enumerate(records) if r.id == id),
            None,
        )
        if idx is None:
            raise KeyError(f"IntakeRecord not found: {id}")

        old = records[idx]
        old_dump = old.model_dump()

        new_status = fields.get("status", old.status)
        is_crisis_transition = (
            old.status != "paused_for_crisis"
            and new_status == "paused_for_crisis"
        )

        merged: dict[str, Any] = dict(old_dump)
        merged.update(fields)
        merged["updated_at"] = self._clock.now()
        new_record = IntakeRecord.model_validate(merged)

        records[idx] = new_record
        self._rewrite_jsonl(self._dir / INTAKE_FILE, records)

        # Status-transition triple FIRST so it precedes any
        # field_extracted on the same update call.
        if is_crisis_transition:
            for event_type in (
                "intake_paused",
                "crisis_detected",
                "referral_issued",
            ):
                self._append_audit_event(
                    event_type=event_type,
                    record_ids=[new_record.id],
                )

        new_dump = new_record.model_dump()
        for field_name, new_value in fields.items():
            if field_name in ("status", "updated_at", "created_at", "id"):
                continue
            if old_dump.get(field_name) == new_dump.get(field_name):
                continue
            field_details: dict[str, Any] = {
                "field_name": field_name,
                "value": _jsonable(new_dump.get(field_name)),
            }
            if source_utterance is not None:
                field_details["source_utterance"] = source_utterance
            if whisper_translation is not None:
                field_details["whisper_translation"] = whisper_translation
            self._append_audit_event(
                event_type="field_extracted",
                record_ids=[new_record.id],
                details=field_details,
            )

        return new_record

    # ─── MatchLink CRUD ──────────────────────────────────────────

    def create_match_link(
        self,
        record_a_id: UUID,
        record_b_id: UUID,
        confidence_band: ConfidenceBand,
        confidence_score: float,
        match_reasoning: dict[str, Any],
        proposed_by: str = "kin_matching_v1",
        candidate_count: int = 1,
        details: dict[str, Any] | None = None,
    ) -> MatchLink:
        """Create + persist a proposed MatchLink. Emits match_proposed.

        candidate_count (Bundle 1.5 S5): the total number of links
        created in this scoring run. Defaults to 1 (the single-link
        case is most common) so existing test fixtures and callers
        stay valid. Pipeline callers pass the run-level total so the
        frontend matchCandidates state can derive the queue rail
        badge value without re-counting events.

        details (B2-S12): optional payload forwarded to the
        match_proposed audit event, surfacing data (e.g. network_match)
        over SSE. Defaults to {} so existing callers stay valid.
        """
        link = MatchLink(
            id=uuid4(),
            record_a_id=record_a_id,
            record_b_id=record_b_id,
            confidence_band=confidence_band,
            confidence_score=confidence_score,
            verification_status="proposed",
            proposed_at=self._clock.now(),
            proposed_by=proposed_by,
            match_reasoning=match_reasoning,
        )
        self._append_jsonl(self._dir / MATCH_FILE, link)
        self._append_audit_event(
            event_type="match_proposed",
            record_ids=[record_a_id, record_b_id],
            match_id=link.id,
            candidate_count=candidate_count,
            details=details or {},
        )
        return link

    def emit_match_proposed_empty(
        self,
        new_record_id: UUID,
        includes_paused_candidates: bool = False,
    ) -> AuditEvent:
        """Emit a match_proposed audit event for a zero-result run.

        Bundle 1.5 S5: the matching trigger now ALWAYS emits
        match_proposed after every scoring run, regardless of result.
        For runs with at least one match, per-match events fire via
        create_match_link (each carrying candidate_count = run total).
        For zero-result runs, this helper emits a single summary
        event with record_ids=[new_record_id] and candidate_count=0
        so the frontend matchCandidates state can confirm "this turn
        produced no candidates" rather than guessing from event
        absence.
        """
        return self._append_audit_event(
            event_type="match_proposed",
            record_ids=[new_record_id],
            candidate_count=0,
            details={"includes_paused_candidates": includes_paused_candidates},
        )

    def update_match_link_status(
        self,
        id: UUID,
        status: VerificationStatus,
        verified_by: str | None = None,
    ) -> MatchLink:
        """Transition verification_status. Emits match_confirmed or
        match_rejected on transition; no event on no-op (e.g.,
        proposed → proposed). Reset transitions (→ proposed) emit
        nothing — not in spec mapping.
        """
        links = self.list_match_links()
        idx = next(
            (i for i, link in enumerate(links) if link.id == id),
            None,
        )
        if idx is None:
            raise KeyError(f"MatchLink not found: {id}")

        old = links[idx]
        if old.verification_status == status:
            return old

        new_link = old.model_copy(
            update={
                "verification_status": status,
                "verified_at": self._clock.now(),
                "verified_by": verified_by,
            }
        )
        links[idx] = new_link
        self._rewrite_jsonl(self._dir / MATCH_FILE, links)

        if status == "confirmed":
            event_type: AuditEventType = "match_confirmed"
        elif status == "rejected":
            event_type = "match_rejected"
        else:
            return new_link

        self._append_audit_event(
            event_type=event_type,
            record_ids=[new_link.record_a_id, new_link.record_b_id],
            match_id=new_link.id,
        )
        return new_link

    def list_match_links(
        self,
        record_id: UUID | None = None,
    ) -> list[MatchLink]:
        all_links = list(self._iter_match_links())
        if record_id is None:
            return all_links
        return [
            link
            for link in all_links
            if link.record_a_id == record_id or link.record_b_id == record_id
        ]

    # ─── AuditEvent read-only ────────────────────────────────────

    def list_audit_events(
        self,
        event_type: AuditEventType | None = None,
        record_id: UUID | None = None,
    ) -> list[AuditEvent]:
        results: list[AuditEvent] = []
        for event in self._iter_audit_events():
            if event_type is not None and event.event_type != event_type:
                continue
            if record_id is not None and record_id not in event.record_ids:
                continue
            results.append(event)
        return results

    # ─── Private helpers ─────────────────────────────────────────

    def _append_audit_event(
        self,
        event_type: AuditEventType,
        record_ids: list[UUID] | None = None,
        match_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        candidate_count: int = 0,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid4(),
            at=self._clock.now(),
            event_type=event_type,
            record_ids=list(record_ids) if record_ids else [],
            match_id=match_id,
            actor=self._actor,
            details=details or {},
            candidate_count=candidate_count,
        )
        self._append_jsonl(self._dir / AUDIT_FILE, event)
        return event

    def _iter_intake_records(self) -> Iterator[IntakeRecord]:
        yield from self._iter_jsonl(self._dir / INTAKE_FILE, IntakeRecord)

    def _iter_match_links(self) -> Iterator[MatchLink]:
        yield from self._iter_jsonl(self._dir / MATCH_FILE, MatchLink)

    def _iter_audit_events(self) -> Iterator[AuditEvent]:
        yield from self._iter_jsonl(self._dir / AUDIT_FILE, AuditEvent)

    @staticmethod
    def _append_jsonl(path: Path, model: Any) -> None:
        line = model.model_dump_json()
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")

    @staticmethod
    def _rewrite_jsonl(path: Path, models: list[Any]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for model in models:
                f.write(model.model_dump_json())
                f.write("\n")

    @staticmethod
    def _iter_jsonl(path: Path, model_cls: Any) -> Iterator[Any]:
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    yield model_cls.model_validate_json(line)
                except ValidationError as e:
                    raise ValueError(
                        f"Invalid JSONL line at {path}:{line_no}: {e}"
                    ) from e


def _jsonable(value: Any) -> Any:
    """Make UUID values JSON-serializable for AuditEvent.details dicts.

    AuditEvent.details flows through model_dump_json downstream, but
    details we construct here may contain raw UUIDs from the changed
    field set. Pre-stringify so the dict is valid JSON before storage.
    """
    if isinstance(value, UUID):
        return str(value)
    return value
