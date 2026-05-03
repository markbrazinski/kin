"""Demo-only endpoints: audit-query (streaming) + fixture seeding.

Registered only when the server is running in dev mode (always on
127.0.0.1:8000 per the FastAPI bind constraint — no additional gating
needed since there is no network egress path).

Routes:
  POST /demo/audit-query  — streams Gemma reasoning about a match pair
  POST /demo/seed-fixture — seeds a named fixture record into storage

Both endpoints return 503 when pipeline adapters are unavailable
(KIN_DISABLE_WARMUP=1 in tests).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

log = structlog.get_logger(__name__)
router = APIRouter()

# ─── POST /demo/audit-query ───────────────────────────────────────────────────

_AUDIT_QUERY_SYSTEM = (
    "You are a humanitarian intake system auditor. Given the audit history "
    "for two matched intake records, explain why they matched. Structure your "
    "response as JSON with the following shape:\n"
    '{"node_matches": [{"pair_label": "...", '
    '"source_utterance_a": "...", "translation_a": "...", "extracted_a": "...", '
    '"source_utterance_b": "...", "translation_b": "...", "extracted_b": "...", '
    '"match_reasoning": "..."}]}\n'
    "Use the exact field names above. Do not add prose outside the JSON. "
    "source_utterance_* fields should contain the original source-script text "
    "from the audit log. translation_* fields should contain the English "
    "translation. extracted_* fields should contain the Gemma-extracted field "
    "value. match_reasoning should name the match signal "
    "(e.g. SAME_SCRIPT_EXACT + age corroborated + complementary roles). "
    "Limit to the top 3 node matches by composite score."
)


class AuditQueryRequest(BaseModel):
    intake_id_a: str
    intake_id_b: str
    query: str = "Why did these records match?"


async def _stream_audit_reasoning(
    *,
    intake_id_a: str,
    intake_id_b: str,
    query: str,
    storage_dir: Path,
) -> Any:
    """Async generator: yields SSE-formatted text lines from Ollama streaming."""
    import ollama as ollama_sdk

    from integration.storage_adapter import StorageAdapter
    from integration.system_clock import SYSTEM_CLOCK

    storage = StorageAdapter(storage_dir, SYSTEM_CLOCK)

    try:
        uuid_a = UUID(intake_id_a)
        uuid_b = UUID(intake_id_b)
    except ValueError:
        yield f"data: {json.dumps({'error': 'invalid intake_id'})}\n\n"
        return

    record_a = storage.read_intake_record(uuid_a)
    record_b = storage.read_intake_record(uuid_b)
    if record_a is None or record_b is None:
        yield f"data: {json.dumps({'error': 'record not found'})}\n\n"
        return

    # Collect field_extracted events for both records.
    def _events_for(record_id: UUID) -> list[dict[str, Any]]:
        return [
            {
                "field": e.details.get("field_name"),
                "value": e.details.get("value"),
                "source_utterance": e.details.get("source_utterance"),
                "whisper_translation": e.details.get("whisper_translation"),
            }
            for e in storage.list_audit_events(
                event_type="field_extracted", record_id=record_id
            )
            if e.details.get("source_utterance")  # only extraction-phase events
        ]

    events_a = _events_for(uuid_a)
    events_b = _events_for(uuid_b)

    context = (
        f"Record A (id={intake_id_a}, lang={record_a.language}, "
        f"status={record_a.status}):\n"
        f"{json.dumps(events_a, ensure_ascii=False, indent=2)}\n\n"
        f"Record B (id={intake_id_b}, lang={record_b.language}, "
        f"status={record_b.status}):\n"
        f"{json.dumps(events_b, ensure_ascii=False, indent=2)}\n\n"
        f"Question: {query}"
    )

    client = ollama_sdk.Client()
    # Stream from Ollama native API (localhost:11434).
    stream = client.chat(
        model="gemma4:e2b",
        messages=[
            {"role": "system", "content": _AUDIT_QUERY_SYSTEM},
            {"role": "user", "content": context},
        ],
        stream=True,
        options={"temperature": 0.1, "num_predict": 600},
    )
    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        if token:
            yield f"data: {json.dumps({'token': token})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/demo/audit-query")
async def audit_query(body: AuditQueryRequest, request: Request) -> StreamingResponse:
    """Stream Gemma reasoning about why two records matched.

    Returns SSE stream of {"token": "..."} lines followed by [DONE].
    The MatchAuditPanel frontend component reads this stream and
    renders tokens into the three-sub-block reasoning display.
    """
    storage_dir: Path = request.app.state.storage_dir

    log.info(
        "audit_query_start",
        intake_id_a=body.intake_id_a,
        intake_id_b=body.intake_id_b,
    )

    return StreamingResponse(
        _stream_audit_reasoning(
            intake_id_a=body.intake_id_a,
            intake_id_b=body.intake_id_b,
            query=body.query,
            storage_dir=storage_dir,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── POST /demo/seed-fixture ──────────────────────────────────────────────────


class SeedFixtureRequest(BaseModel):
    fixture_name: str
    """One of: yusuf, mariam, ambient_a, ambient_b"""


_FIXTURE_FNS: dict[str, Any] = None  # type: ignore[assignment]  — lazy import


def _get_fixture_fns() -> dict[str, Any]:
    global _FIXTURE_FNS
    if _FIXTURE_FNS is None:
        from integration.fixture_seed import (
            seed_ambient_a,
            seed_ambient_b,
            seed_mariam,
            seed_yusuf,
        )

        _FIXTURE_FNS = {
            "yusuf": seed_yusuf,
            "mariam": seed_mariam,
            "ambient_a": seed_ambient_a,
            "ambient_b": seed_ambient_b,
        }
    return _FIXTURE_FNS


@router.post("/demo/seed-fixture")
async def seed_fixture(body: SeedFixtureRequest, request: Request) -> dict[str, Any]:
    """Seed a named fixture record into storage (idempotent).

    Used by DemoDock recording-day fallback buttons. Returns the seeded
    record's id, status, and language for queue-rail refresh.
    """
    from integration.storage_adapter import StorageAdapter
    from integration.system_clock import SYSTEM_CLOCK

    storage_dir: Path = request.app.state.storage_dir
    fns = _get_fixture_fns()

    fn = fns.get(body.fixture_name)
    if fn is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown fixture_name={body.fixture_name!r}; "
            f"valid: {sorted(fns)}",
        )

    storage = StorageAdapter(storage_dir, SYSTEM_CLOCK)
    record = fn(storage)

    log.info(
        "demo_fixture_seeded",
        fixture_name=body.fixture_name,
        record_id=str(record.id),
        status=record.status,
    )

    return {
        "fixture_name": body.fixture_name,
        "record_id": str(record.id),
        "status": record.status,
        "language": record.language,
    }
