"""Tests for the FastAPI scaffolding — /healthz only.

The /intake/stream stub-era tests (`field_update`/`complete` placeholders)
were superseded in Bundle 1 S1 by the merged-stream contract; see
test_sse.py for the SSE event-shape coverage.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from ui.server.main import app


def test_healthz_returns_200() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
