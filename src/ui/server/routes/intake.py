"""Intake SSE stream — Day 10 stub; real pipeline wiring lands Day 11+."""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

log = structlog.get_logger(__name__)
router = APIRouter()

_FIELD_SEQUENCE: list[tuple[str, str]] = [
    ("name", "stub"),
    ("age", "stub"),
    ("last_seen", "stub"),
    ("distinguishing_marks", "stub"),
]


async def _stub_stream():
    log.info("intake_stream_start", events=len(_FIELD_SEQUENCE) + 1)
    for field, value in _FIELD_SEQUENCE:
        await asyncio.sleep(0.5)
        yield {
            "event": "field_update",
            "data": json.dumps({"field": field, "value": value}),
        }
    await asyncio.sleep(0.5)
    yield {"event": "complete", "data": "{}"}
    log.info("intake_stream_complete")


@router.get("/intake/stream")
async def intake_stream() -> EventSourceResponse:
    return EventSourceResponse(_stub_stream())
