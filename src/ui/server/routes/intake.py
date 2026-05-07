"""Intake SSE stream + audio upload + worker transliteration POST."""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from integration.transcription_pipeline import (
    _maybe_retrigger_matching,
    ingest_audio,
)
from ui.server.sse import merged_stream

log = structlog.get_logger(__name__)
router = APIRouter()


class AudioUploadResponse(BaseModel):
    """Response shape for POST /intake/audio.

    `locale_aware_message` is populated when is_crisis is True;
    it carries Gemma's escalate_crisis short message in the speaker's
    language for the overlay to render.
    Ephemeral — not persisted (ADR-004 REV 2 + REV 3).
    """

    intake_id: str
    status: str
    is_crisis: bool = False
    locale_aware_message: str | None = None


@router.get("/intake/stream")
async def intake_stream(
    request: Request,
    source_device_id: str | None = None,
) -> EventSourceResponse:
    storage_dir: Path = request.app.state.storage_dir
    log.info(
        "intake_stream_open",
        source_device_id=source_device_id,
        storage_dir=str(storage_dir),
    )
    return EventSourceResponse(
        merged_stream(
            storage_dir=storage_dir,
            source_device_id=source_device_id,
        )
    )


# ─── Audio upload ────────────────────────────────────────────────


@router.post("/intake/audio")
async def upload_audio(
    request: Request,
    audio: UploadFile = File(...),
    lang: str = Form(...),
    source_device_id: str = Form(...),
    intake_id: str | None = Form(None),
) -> AudioUploadResponse:
    """Browser MediaRecorder posts a blob (typically audio/webm) here.

    Backend transcodes to 16kHz mono s16 WAV via ffmpeg subprocess
    (ffmpeg is already required by whisper_adapter._preprocess for
    head-silence padding), then dispatches into ingest_audio. When
    ``intake_id`` is supplied, dispatches the extend path; the new
    turn merges its extracted fields into the existing record and
    fires re-trigger matching if any identity-bearing field changed.
    """
    whisper = request.app.state.whisper
    ollama = request.app.state.ollama
    storage = request.app.state.storage
    if whisper is None or ollama is None or storage is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "pipeline adapters unavailable; backend started in "
                "KIN_DISABLE_WARMUP=1 mode"
            ),
        )

    parsed_intake_id: UUID | None = None
    if intake_id:
        try:
            parsed_intake_id = UUID(intake_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid intake_id: {exc}"
            ) from exc

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Write the upload to disk; preserve the source extension so
        # ffmpeg sniffs format correctly (webm, mp4, ogg, wav all work).
        suffix = Path(audio.filename or "in.webm").suffix or ".webm"
        src_path = tmp_dir / f"upload{suffix}"
        wav_path = tmp_dir / "decoded.wav"
        src_path.write_bytes(await audio.read())

        # Transcode to 16kHz mono s16 WAV. faster-whisper-medium expects
        # this shape after whisper_adapter._preprocess pads it.
        await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg", "-y",
                "-i", str(src_path),
                "-ar", "16000",
                "-ac", "1",
                "-sample_fmt", "s16",
                "-f", "wav",
                str(wav_path),
            ],
            check=True,
            capture_output=True,
        )

        record, locale_message = await ingest_audio(
            audio_path=wav_path,
            lang=lang,
            source_device_id=source_device_id,
            whisper=whisper,
            ollama=ollama,
            storage=storage,
            intake_id=parsed_intake_id,
        )

    # Defensive status-gating: ingest_audio only returns a non-None
    # message on the crisis branch, but explicit gating in the
    # response layer keeps the contract obvious to readers.
    return AudioUploadResponse(
        intake_id=str(record.id),
        status=record.status,
        is_crisis=record.is_crisis,
        locale_aware_message=(
            locale_message if record.is_crisis else None
        ),
    )


# ─── Worker transliteration ──────────────────────────────────────


class TransliterationBody(BaseModel):
    value: str


@router.post("/intake/{intake_id}/transliteration")
async def update_transliteration(
    intake_id: UUID,
    body: TransliterationBody,
    request: Request,
) -> dict[str, Any]:
    """Worker entered a Latin-script transliteration of a non-Latin
    source-script name. Persist via storage and fire matching
    re-trigger so a Tent A vs Tent B dual-script match can land.
    """
    storage = request.app.state.storage
    if storage is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "pipeline adapters unavailable; backend started in "
                "KIN_DISABLE_WARMUP=1 mode"
            ),
        )

    existing = storage.read_intake_record(intake_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"intake_id {intake_id} not found"
        )

    if existing.full_name_transliteration == body.value:
        # No-op; storage's no-op detection would skip the update too,
        # but short-circuit here so we don't fire a spurious matching
        # re-trigger log line.
        return {"intake_id": str(existing.id), "changed": False}

    record = storage.update_intake_record(
        intake_id, full_name_transliteration=body.value
    )
    await _maybe_retrigger_matching(
        record,
        changed_fields={"full_name_transliteration"},
        storage=storage,
    )
    return {"intake_id": str(record.id), "changed": True}


# ─── Crisis resolution ────────────────────────────────────────────


class CrisisResolvedBody(BaseModel):
    resolution: Literal["referral_provided", "de_escalated"]
    referral_organization: str | None = None


@router.post("/intake/{intake_id}/crisis-resolved")
async def crisis_resolved(
    intake_id: UUID,
    body: CrisisResolvedBody,
    request: Request,
) -> dict[str, Any]:
    """Record how the worker resolved a crisis referral.

    Emits a crisis_resolved audit event so the caseworker review
    surface can show whether a referral was issued or the situation
    de-escalated. The intake record itself is unaffected.
    """
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(status_code=503, detail="pipeline adapters unavailable")

    existing = storage.read_intake_record(intake_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"intake_id {intake_id} not found")

    storage.emit_crisis_resolved(
        existing.id,
        resolution=body.resolution,
        referral_organization=body.referral_organization,
    )
    return {"ok": True}
