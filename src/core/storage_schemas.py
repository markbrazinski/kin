"""Pydantic v2 storage schemas — IntakeRecord, MatchLink, AuditEvent.

Per Part 1 REV 4 (KIN Demo storage state spec). Three persisted record
types backing the JSONL files in storage/:

  * IntakeRecord    → storage/intake_records.jsonl
  * MatchLink       → storage/match_links.jsonl
  * AuditEvent      → storage/audit_events.jsonl

All models use ConfigDict(extra='ignore') so spec evolution doesn't
break round-trips. Pure Core: no I/O, no integration imports. Storage
adapter (Integration) consumes these for JSONL serialization via
model_dump_json() / model_validate_json(); enum-shaped fields use
Literal types per repo convention (rfl_schema.py, safety_rules.py,
matching.py).

match_reasoning concrete shape (locked S2):
    {"matched_fields": list[str], "phonetic_score": float,
     "reason": str}
Direct lift from MatchResult in core.matching. Kept as dict (not
nested model) to avoid storage_schemas ↔ matching import coupling.

Audit-event mapping is the storage adapter's responsibility — see
src/integration/storage_adapter.py for the auto-emit logic on each
CRUD operation. AuditEventType.minor_flagged is intentionally absent;
"minor flagged" is a structlog-only signal emitted in orchestration,
not a persisted audit event (resolved in plan discrepancy #1).
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.rfl_schema import FamilyMember

# ─── Type aliases (Literal enums, repo convention) ───────────────

IntakeStatus = Literal["complete", "partial"]
SupportedLanguage = Literal["en", "es", "ar", "fa", "fr", "uk"]
CrisisMatchPath = Literal["keyword", "semantic"]
VerificationStatus = Literal["proposed", "confirmed", "rejected"]
ConfidenceBand = Literal["low", "medium", "high"]
AuditEventType = Literal[
    "intake_created",
    "crisis_detected",
    "referral_issued",
    "crisis_resolved",
    "match_proposed",
    "match_confirmed",
    "match_rejected",
    "field_extracted",
]


# ─── IntakeRecord ────────────────────────────────────────────────


class IntakeRecord(BaseModel):
    """A single intake session captured to storage.

    Identity-field empty-string defaults (full_name_source_script,
    full_name_transliteration, relationship_to_seeker) instead of None:
    Part 1 REV 4 types these as str (not str | None), and the
    progressive-fill flow needs the record to validate at create time
    before extraction populates them. Empty string preserves type while
    signaling "not yet set"; status="complete" derivation in the
    orchestration layer treats empty-string as not-yet-set.

    Crisis records have identity fields left empty (per Part 1 §Beat 7
    "whatever Whisper produced"); is_crisis=True; referral_* populated.
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    created_at: datetime
    updated_at: datetime
    status: IntakeStatus
    language: SupportedLanguage
    source_device_id: str

    full_name_source_script: str = ""
    full_name_transliteration: str = ""
    relationship_to_seeker: str = ""
    age: int | None = None
    last_seen_location: str | None = None
    last_seen_date: str | None = None
    distinguishing_marks: str | None = None

    is_minor: bool = False
    is_crisis: bool = False
    crisis_match_path: CrisisMatchPath | None = None
    referral_issued: bool = False
    referral_organization: str | None = None

    family_roster: list[FamilyMember] = Field(default_factory=list)
    """Additional family members mentioned during intake. Empty list for
    pre-S9 records and intakes where no secondary members were named."""

    searcher_name: str = ""
    searcher_name_transliteration: str = ""
    searcher_relationship_to_target: str = ""
    separation_circumstance: str | None = None


# ─── MatchLink ───────────────────────────────────────────────────


class MatchLink(BaseModel):
    """A proposed or verified match between two IntakeRecords.

    match_reasoning is a plain dict (not a nested model) by design —
    keeping the shape as data avoids coupling storage_schemas to
    core.matching's MatchResult model. The orchestration layer
    (S5 _trigger_matching) is responsible for shaping the dict from
    MatchResult fields; consumers (UI, audit replay) read it as JSON.
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    record_a_id: UUID
    record_b_id: UUID
    confidence_band: ConfidenceBand
    confidence_score: float
    verification_status: VerificationStatus
    proposed_at: datetime
    proposed_by: str
    verified_at: datetime | None = None
    verified_by: str | None = None
    match_reasoning: dict[str, Any] = Field(default_factory=dict)


# ─── AuditEvent ──────────────────────────────────────────────────


class AuditEvent(BaseModel):
    """An audit log entry for an operation on an IntakeRecord or MatchLink.

    Drives both (a) audit trails for caseworker review and (b) the
    structlog sidebar during live ingest beats (Beat 5/6/7). NOT used
    to replay historical record creation — pre-seeded records get a
    single intake_created event at seed time, no field_extracted
    sequence (per Part 1 REV 4 §"Audit events at seed time").

    record_ids is a list because match_proposed / match_confirmed /
    match_rejected events refer to two records simultaneously, EXCEPT
    for empty-result match_proposed events (Bundle 1.5 S5) where the
    list contains only the new record's id and candidate_count is 0.

    candidate_count (Bundle 1.5 S5): For match_proposed events, the
    total number of match candidates the matching trigger produced
    for the new record. 0 for empty-result emissions; otherwise the
    count of links created in this scoring run. Frontend
    matchCandidates state derives the queue rail badge value from
    this field. Defaulted to 0 so existing event types and JSONL
    records remain valid (additive change).
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    at: datetime
    event_type: AuditEventType
    record_ids: list[UUID] = Field(default_factory=list)
    match_id: UUID | None = None
    actor: str = "kin_system"
    details: dict[str, Any] = Field(default_factory=dict)
    candidate_count: int = 0
