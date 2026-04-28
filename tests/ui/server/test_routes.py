"""Tests for the FastAPI scaffolding — /healthz and /intake/stream stub."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from httpx_sse import aconnect_sse

from ui.server.main import app


def test_healthz_returns_200() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def _collect_intake_events() -> list[tuple[str, str]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with aconnect_sse(client, "GET", "/intake/stream") as event_source:
            return [(ev.event, ev.data) async for ev in event_source.aiter_sse()]


@pytest.mark.asyncio
async def test_intake_stream_emits_5_events() -> None:
    events = await _collect_intake_events()
    assert len(events) == 5
    types = [ev_type for ev_type, _ in events]
    assert types == ["field_update"] * 4 + ["complete"]


@pytest.mark.asyncio
async def test_intake_stream_event_shape() -> None:
    events = await _collect_intake_events()
    first_type, first_data = events[0]
    assert first_type == "field_update"
    payload = json.loads(first_data)
    assert set(payload.keys()) == {"field", "value"}
    assert payload["field"] == "name"


@pytest.mark.asyncio
async def test_intake_stream_terminates() -> None:
    events = await _collect_intake_events()
    last_type, last_data = events[-1]
    assert last_type == "complete"
    assert last_data == "{}"
