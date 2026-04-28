"""Intake SSE stream — merged audit + structlog events from the runtime."""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ui.server.sse import merged_stream

log = structlog.get_logger(__name__)
router = APIRouter()


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
