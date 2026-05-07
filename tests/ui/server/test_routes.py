"""Tests for the FastAPI scaffolding — /healthz + /intake/audio response shape.

The /intake/stream stub-era tests (`field_update`/`complete` placeholders)
were superseded in Bundle 1 S1 by the merged-stream contract; see
test_sse.py for the SSE event-shape coverage.

The /intake/audio test (S6-fix2 / ADR-004 REV 3) covers the response-shape
contract on the crisis branch: is_crisis=True must surface Gemma's
locale_aware_message; non-crisis branches must return locale_aware_message=null. The full pipeline is monkey-patched out —
this is a route-layer contract test, not an integration test.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.storage_schemas import IntakeRecord
from ui.server.main import app, app_factory


def test_healthz_returns_200() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _make_record(*, status: str, language: str = "ar", is_crisis: bool = False) -> IntakeRecord:
    """Minimal IntakeRecord with the fields the route reads (id, status, is_crisis)."""
    now = datetime.now(timezone.utc)
    return IntakeRecord(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        language=language,  # type: ignore[arg-type]
        source_device_id="tent_b",
        status=status,  # type: ignore[arg-type]
        is_crisis=is_crisis,
    )


def test_upload_audio_response_shape_crisis_and_non_crisis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route surfaces locale_aware_message only when is_crisis=True.

    Both branches exercised in one test — the negative (non-crisis →
    null) is the same contract from the other side.
    """
    crisis_record = _make_record(status="partial", language="ar", is_crisis=True)
    happy_record = _make_record(status="complete", language="es")

    next_return: list[tuple[IntakeRecord, str | None]] = [
        (crisis_record, "يرجى الاتصال بالرقم الموحد"),
        (happy_record, None),
    ]
    call_count = {"n": 0}

    async def fake_ingest_audio(*_args: Any, **_kwargs: Any) -> tuple[IntakeRecord, str | None]:
        idx = call_count["n"]
        call_count["n"] += 1
        return next_return[idx]

    async def fake_to_thread(_func: Any, *_a: Any, **_k: Any) -> int:
        # Skip the ffmpeg subprocess; the route writes a wav_path that
        # nothing reads because ingest_audio is patched out.
        return 0

    from ui.server.routes import intake as intake_module
    monkeypatch.setattr(intake_module, "ingest_audio", fake_ingest_audio)
    monkeypatch.setattr(intake_module.asyncio, "to_thread", fake_to_thread)

    # Stand up an app bound to tmp_path and seed the adapters so the
    # 503 guard at routes/intake.py doesn't fire.
    app_under_test = app_factory(tmp_path)
    app_under_test.state.whisper = object()
    app_under_test.state.ollama = object()
    app_under_test.state.storage = object()

    client = TestClient(app_under_test)

    # Crisis branch.
    r1 = client.post(
        "/intake/audio",
        files={"audio": ("turn.webm", io.BytesIO(b"\x00" * 32), "audio/webm")},
        data={"lang": "ar", "source_device_id": "tent_b"},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["status"] == "partial"
    assert body1["is_crisis"] is True
    assert body1["intake_id"] == str(crisis_record.id)
    assert body1["locale_aware_message"] == "يرجى الاتصال بالرقم الموحد"

    # Non-crisis branch.
    r2 = client.post(
        "/intake/audio",
        files={"audio": ("turn.webm", io.BytesIO(b"\x00" * 32), "audio/webm")},
        data={"lang": "es", "source_device_id": "tent_a"},
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["status"] == "complete"
    assert body2["intake_id"] == str(happy_record.id)
    assert body2["locale_aware_message"] is None


def test_get_intake_records_returns_record_list(
    tmp_path: Path,
) -> None:
    """GET /intake/records returns 200 + {records: [...]} shape.

    Uses a real StorageAdapter against tmp_path so the endpoint reads
    actual persisted records rather than a mock.
    """
    from integration.storage_adapter import StorageAdapter
    from tests.fakes.fake_clock import FakeClock

    storage = StorageAdapter(tmp_path / "storage", FakeClock())
    record = storage.create_intake_record(
        language="es",
        source_device_id="tent_a",
    )

    app_under_test = app_factory(tmp_path)
    app_under_test.state.whisper = object()
    app_under_test.state.ollama = object()
    app_under_test.state.storage = storage

    client = TestClient(app_under_test)
    r = client.get("/intake/records")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "records" in body
    assert isinstance(body["records"], list)
    assert len(body["records"]) == 1
    assert body["records"][0]["id"] == str(record.id)
    assert body["records"][0]["status"] == "partial"
