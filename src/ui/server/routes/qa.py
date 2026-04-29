"""QA injection endpoint — only registered when KIN_QA_MODE=1.

Used during Bundle 1 S4 manual smoke (QA-1). Audit-only injection
could be done via direct file appends, but structlog events MUST
originate inside the uvicorn process so the configure_for_sse()
fanout processor sees them. An HTTP endpoint is the simplest
in-process inject path.

Lifecycle:
- main.py reads ``KIN_QA_MODE`` and registers this router only when
  the env flag is "1".
- Endpoint binds to 127.0.0.1 like the rest of the app (no extra
  exposure beyond what /intake/stream already accepts).
- Off by default: production runs without the env flag never include
  this router.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post("/qa/inject")
async def qa_inject(request: Request) -> dict[str, Any]:
    """Inject a synthetic audit or structlog event.

    Body shape:
        {"kind": "audit", "payload": {...AuditEvent fields}}
        {"kind": "structlog", "payload": {"event": "<name>", "fields": {...}}}

    Audit payloads MAY include ``source_device_id`` and ``language``;
    when present, an IntakeRecord with a matching ``record_ids[0]`` is
    auto-seeded if no record with that id exists yet. This makes the
    source_device_id filter on /intake/stream work for QA-1 events
    without forcing the operator to pre-seed records by hand.
    """
    storage_dir: Path = request.app.state.storage_dir
    body = await request.json()
    kind = body.get("kind")
    payload: dict[str, Any] = body.get("payload") or {}

    if kind == "audit":
        return _inject_audit(storage_dir, payload)
    if kind == "structlog":
        return _inject_structlog(payload)

    raise HTTPException(status_code=400, detail=f"unknown kind={kind!r}")


def _inject_audit(storage_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    storage_dir.mkdir(parents=True, exist_ok=True)
    intake_path = storage_dir / "intake_records.jsonl"
    audit_path = storage_dir / "audit_events.jsonl"

    now = datetime.now(timezone.utc).isoformat()

    record_ids = payload.get("record_ids") or [str(uuid4())]
    source_device_id = payload.get("source_device_id")
    language = payload.get("language", "es")

    # Auto-seed an IntakeRecord for the first record_id if it isn't
    # already present in the JSONL — makes the source_device_id filter
    # find the matching device id without manual pre-seeding.
    if source_device_id:
        existing_ids = _existing_intake_record_ids(intake_path)
        first_id = record_ids[0]
        if first_id not in existing_ids:
            record = {
                "id": first_id,
                "created_at": now,
                "updated_at": now,
                "status": "partial",
                "language": language,
                "source_device_id": source_device_id,
                "full_name_source_script": "",
                "full_name_transliteration": "",
                "relationship_to_seeker": "",
                "is_minor": False,
                "is_crisis": False,
                "referral_issued": False,
            }
            with intake_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record))
                f.write("\n")

    audit = {
        "id": str(uuid4()),
        "at": payload.get("at", now),
        "event_type": payload.get("event_type", "field_extracted"),
        "record_ids": record_ids,
        "match_id": payload.get("match_id"),
        "actor": payload.get("actor", "kin_qa"),
        "details": payload.get("details", {}),
    }
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(audit))
        f.write("\n")

    return {"injected": "audit", "audit_id": audit["id"]}


def _inject_structlog(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event")
    if not event:
        raise HTTPException(
            status_code=400, detail="structlog payload requires 'event'"
        )
    fields = payload.get("fields") or {}
    structlog.get_logger("qa_inject").info(event, **fields)
    return {"injected": "structlog", "event": event}


def _existing_intake_record_ids(intake_path: Path) -> set[str]:
    if not intake_path.exists():
        return set()
    ids: set[str] = set()
    with intake_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rid = json.loads(line).get("id")
                if isinstance(rid, str):
                    ids.add(rid)
            except json.JSONDecodeError:
                continue
    return ids
