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
from typing import Any, Literal
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


# ─── POST /demo/clear-storage ────────────────────────────────────────────────


@router.post("/demo/clear-storage")
async def clear_storage(request: Request) -> dict[str, Any]:
    """Truncate all three JSONL storage files.

    Called by the ⌘⇧X keybinding before a recording take so the matcher
    starts from a clean slate without requiring a manual shell command.
    """
    from integration.storage_adapter import StorageAdapter
    from integration.system_clock import SYSTEM_CLOCK

    storage_dir: Path = request.app.state.storage_dir
    storage = StorageAdapter(storage_dir, SYSTEM_CLOCK)
    storage.clear_all()

    log.info("storage_cleared", storage_dir=str(storage_dir))
    return {"status": "cleared"}


# ─── POST /demo/run-intake ────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[4]

_DEMO_AUDIO: dict[str, Path] = {
    "yusuf": _REPO_ROOT / "audio_samples/demo_samples/Arabic VO_Yusuf_take_4_demo.mp3",
    "mariam": _REPO_ROOT / "audio_samples/demo_samples/Arabic VO_Mariam_take 2 demo.wav",
}


class DemoRunIntakeBody(BaseModel):
    filename: Literal["yusuf", "mariam"]
    lang: str = "ar"
    source_device_id: str = "laptop"
    intake_id: str | None = None


@router.post("/demo/run-intake")
async def demo_run_intake(
    body: DemoRunIntakeBody, request: Request
) -> dict[str, Any]:
    """Run the real ingest pipeline on a pre-recorded demo audio file.

    Resolves the filename alias to a path on disk and calls ingest_audio()
    exactly as /intake/audio does. Returns the same AudioUploadResponse
    shape so the frontend demo path is indistinguishable from a live intake.

    Returns 503 when pipeline adapters are unavailable (KIN_DISABLE_WARMUP=1).
    Returns 404 when the resolved audio file does not exist on disk.
    Returns 422 when Gemma cannot extract intake fields (InvalidToolCall).
    """
    from integration._errors import InvalidToolCall
    from integration.transcription_pipeline import ingest_audio

    whisper = request.app.state.whisper
    ollama = request.app.state.ollama
    storage = request.app.state.storage
    if None in (whisper, ollama, storage):
        raise HTTPException(
            status_code=503,
            detail="pipeline adapters unavailable; server started with KIN_DISABLE_WARMUP=1",
        )

    audio_path = _DEMO_AUDIO[body.filename]
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"demo audio file not found: {audio_path}",
        )

    parsed_intake_id: UUID | None = None
    if body.intake_id:
        try:
            parsed_intake_id = UUID(body.intake_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid intake_id: {exc}"
            ) from exc

    log.info(
        "demo_run_intake_start",
        filename=body.filename,
        audio_path=str(audio_path),
        lang=body.lang,
        source_device_id=body.source_device_id,
    )

    try:
        record, locale_message = await ingest_audio(
            audio_path=audio_path,
            lang=body.lang,
            source_device_id=body.source_device_id,
            whisper=whisper,
            ollama=ollama,
            storage=storage,
            intake_id=parsed_intake_id,
        )
    except InvalidToolCall as exc:
        log.warning(
            "demo_intake_no_tool_call",
            filename=body.filename,
            error=str(exc),
        )
        raise HTTPException(
            status_code=422,
            detail="Audio transcribed but Gemma could not extract intake fields.",
        ) from exc

    return {
        "intake_id": str(record.id),
        "status": record.status,
        "is_crisis": record.is_crisis,
        "locale_aware_message": locale_message if record.is_crisis else None,
    }
