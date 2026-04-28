"""Tests for /intake/stream — merged audit + structlog SSE.

Each test runs against a real uvicorn on an ephemeral port (see
conftest.py): httpx.ASGITransport buffers responses and deadlocks on
open-ended streaming endpoints, so we exercise the full HTTP path.

The ``sse_server`` fixture yields ``(base_url, tmp_path)``; tests drive
events into ``tmp_path/audit_events.jsonl`` and via structlog calls,
then assert the wire shape that S2 will consume.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog
from httpx import AsyncClient
from httpx_sse import aconnect_sse

from core.storage_schemas import AuditEvent, IntakeRecord
from ui.server.structlog_config import configure_for_sse

# ─── Helpers ──────────────────────────────────────────────────────


def _utc(year: int = 2026, month: int = 5, day: int = 2) -> datetime:
    return datetime(year, month, day, 12, 0, 0, tzinfo=UTC)


def _make_intake_record(
    *,
    source_device_id: str,
    record_id: UUID | None = None,
    language: str = "es",
) -> IntakeRecord:
    rid = record_id or uuid4()
    return IntakeRecord(
        id=rid,
        created_at=_utc(),
        updated_at=_utc(),
        status="partial",
        language=language,  # type: ignore[arg-type]
        source_device_id=source_device_id,
    )


def _make_audit_event(
    *,
    event_type: str,
    record_ids: list[UUID],
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        at=_utc(),
        event_type=event_type,  # type: ignore[arg-type]
        record_ids=record_ids,
        details=details or {},
    )


def _append_jsonl(path: Path, model: Any) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(model.model_dump_json())
        f.write("\n")


async def _collect(
    base_url: str,
    *,
    source_device_id: str | None,
    expected: int,
    drive: Any,
    storage_dir: Path,
    timeout: float = 5.0,
) -> list[tuple[str, dict[str, Any]]]:
    """Open SSE, run drive(storage_dir), collect ``expected`` events."""
    url = "/intake/stream"
    if source_device_id is not None:
        url = f"{url}?source_device_id={source_device_id}"

    collected: list[tuple[str, dict[str, Any]]] = []
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        async with aconnect_sse(client, "GET", url) as event_source:
            assert event_source.response.status_code == 200
            # Server-side merged_stream has registered its structlog
            # queue and seeked to end-of-file by the time the response
            # headers have flushed. Drive events now.
            drive_task = asyncio.create_task(drive(storage_dir))

            try:
                aiter = event_source.aiter_sse()
                while len(collected) < expected:
                    ev = await asyncio.wait_for(aiter.__anext__(), timeout=timeout)
                    collected.append((ev.event, json.loads(ev.data)))
            finally:
                if not drive_task.done():
                    await drive_task
    return collected


async def _expect_no_events(
    base_url: str,
    *,
    source_device_id: str | None,
    drive: Any,
    storage_dir: Path,
    wait: float = 0.6,
) -> None:
    url = "/intake/stream"
    if source_device_id is not None:
        url = f"{url}?source_device_id={source_device_id}"

    async with AsyncClient(base_url=base_url, timeout=5.0) as client:
        async with aconnect_sse(client, "GET", url) as event_source:
            assert event_source.response.status_code == 200
            drive_task = asyncio.create_task(drive(storage_dir))
            try:
                aiter = event_source.aiter_sse()
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(aiter.__anext__(), timeout=wait)
            finally:
                if not drive_task.done():
                    await drive_task


@pytest.fixture(autouse=True)
def _ensure_structlog_configured() -> None:
    """Tests in this file emit structlog events from the test process,
    expecting them to appear in the SSE stream from the server process.
    BUT — uvicorn runs in the same Python process (just a different
    thread), so the module-level ``_active_structlog_queues`` set is
    shared. Calling configure_for_sse() here is idempotent.
    """
    configure_for_sse()


# ─── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_opens_and_closes_cleanly(
    sse_server: tuple[str, Path],
) -> None:
    base_url, _ = sse_server
    async with AsyncClient(base_url=base_url, timeout=5.0) as client:
        async with aconnect_sse(client, "GET", "/intake/stream") as event_source:
            assert event_source.response.status_code == 200


@pytest.mark.asyncio
async def test_audit_event_with_details_passes_through_unmodified(
    sse_server: tuple[str, Path],
) -> None:
    """match_proposed event with match_reasoning-shaped details rides
    through the SSE envelope byte-equivalent on the inner dict.

    Locks the contract for affordance (c) Beat-6 sidebar reasoning render.
    """
    base_url, storage_dir = sse_server
    record_a = uuid4()
    record_b = uuid4()
    reasoning = {
        "matched_fields": ["full_name_source_script", "age", "relationship"],
        "phonetic_score": 0.92,
        "reason": "source-script identity + age + relationship",
    }
    event = _make_audit_event(
        event_type="match_proposed",
        record_ids=[record_a, record_b],
        details=reasoning,
    )

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", event)

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=1,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 1
    ev_type, payload = events[0]
    assert ev_type == "audit_event"
    assert payload["type"] == "audit_event"
    assert payload["payload"]["event_type"] == "match_proposed"
    assert payload["payload"]["details"] == reasoning


@pytest.mark.asyncio
async def test_structlog_event_appears_in_stream(
    sse_server: tuple[str, Path],
) -> None:
    base_url, storage_dir = sse_server
    log = structlog.get_logger("test_sse_structlog")

    async def drive(_sd: Path) -> None:
        await asyncio.sleep(0.1)
        log.info("custom_event", extra_field="hello")

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=1,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 1
    ev_type, payload = events[0]
    assert ev_type == "structlog_event"
    assert payload["type"] == "structlog_event"
    assert payload["payload"]["event"] == "custom_event"
    assert payload["payload"]["extra_field"] == "hello"


@pytest.mark.asyncio
async def test_audit_and_structlog_interleave(
    sse_server: tuple[str, Path],
) -> None:
    """Both sources arrive in emission order with no drop or reorder."""
    base_url, storage_dir = sse_server
    log = structlog.get_logger("test_sse_interleave")
    audit = _make_audit_event(event_type="intake_created", record_ids=[uuid4()])

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", audit)
        await asyncio.sleep(0.15)
        log.info("after_audit", n=1)

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=2,
        drive=drive,
        storage_dir=storage_dir,
    )
    types = [t for t, _ in events]
    assert types == ["audit_event", "structlog_event"]
    assert events[1][1]["payload"]["event"] == "after_audit"


@pytest.mark.asyncio
async def test_source_device_id_filter_passes_matching(
    sse_server: tuple[str, Path],
) -> None:
    base_url, storage_dir = sse_server
    record = _make_intake_record(source_device_id="laptop-A")
    _append_jsonl(storage_dir / "intake_records.jsonl", record)

    audit = _make_audit_event(
        event_type="field_extracted",
        record_ids=[record.id],
        details={"field_name": "full_name_source_script", "value": "Carlos"},
    )

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", audit)

    events = await _collect(
        base_url,
        source_device_id="laptop-A",
        expected=1,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 1
    _, payload = events[0]
    assert payload["source_device_id"] == "laptop-A"
    assert payload["payload"]["event_type"] == "field_extracted"


@pytest.mark.asyncio
async def test_source_device_id_filter_drops_other_device(
    sse_server: tuple[str, Path],
) -> None:
    base_url, storage_dir = sse_server
    record_b = _make_intake_record(source_device_id="laptop-B")
    _append_jsonl(storage_dir / "intake_records.jsonl", record_b)

    audit = _make_audit_event(
        event_type="field_extracted",
        record_ids=[record_b.id],
        details={"field_name": "full_name_source_script", "value": "Mohamad"},
    )

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", audit)

    await _expect_no_events(
        base_url,
        source_device_id="laptop-A",
        drive=drive,
        storage_dir=storage_dir,
    )


@pytest.mark.asyncio
async def test_no_filter_passes_all_events(
    sse_server: tuple[str, Path],
) -> None:
    base_url, storage_dir = sse_server
    record_a = _make_intake_record(source_device_id="laptop-A")
    record_b = _make_intake_record(source_device_id="laptop-B")
    _append_jsonl(storage_dir / "intake_records.jsonl", record_a)
    _append_jsonl(storage_dir / "intake_records.jsonl", record_b)

    audit_a = _make_audit_event(
        event_type="field_extracted", record_ids=[record_a.id]
    )
    audit_b = _make_audit_event(
        event_type="field_extracted", record_ids=[record_b.id]
    )

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", audit_a)
        await asyncio.sleep(0.1)
        _append_jsonl(sd / "audit_events.jsonl", audit_b)

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=2,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 2
    devices = {payload["source_device_id"] for _, payload in events}
    assert devices == {"laptop-A", "laptop-B"}


@pytest.mark.asyncio
async def test_no_history_replay_on_connect(
    sse_server: tuple[str, Path],
) -> None:
    """Pre-existing audit lines are NOT replayed at connection-open.

    Locks Bundle 1 decision #4 (no history replay).
    """
    base_url, storage_dir = sse_server
    pre1 = _make_audit_event(event_type="intake_created", record_ids=[uuid4()])
    pre2 = _make_audit_event(event_type="intake_created", record_ids=[uuid4()])
    pre3 = _make_audit_event(event_type="intake_created", record_ids=[uuid4()])
    audit_path = storage_dir / "audit_events.jsonl"
    _append_jsonl(audit_path, pre1)
    _append_jsonl(audit_path, pre2)
    _append_jsonl(audit_path, pre3)

    new_event = _make_audit_event(
        event_type="field_extracted", record_ids=[uuid4()]
    )

    async def drive(sd: Path) -> None:
        await asyncio.sleep(0.2)
        _append_jsonl(sd / "audit_events.jsonl", new_event)

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=1,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 1
    _, payload = events[0]
    assert payload["payload"]["id"] == str(new_event.id)
    assert payload["payload"]["event_type"] == "field_extracted"


@pytest.mark.asyncio
async def test_malformed_audit_line_is_skipped_not_crashing(
    sse_server: tuple[str, Path],
) -> None:
    """A bad JSON line in audit_events.jsonl drops without killing the stream.

    Tests the _audit_tail() drop-and-log branch (our code, not sse-starlette's).
    Two events are expected on the wire:
      1. the structlog warning ``audit_tail_malformed_line`` from our code
      2. the good audit event written next, proving the stream survived
    """
    base_url, storage_dir = sse_server
    good = _make_audit_event(event_type="intake_created", record_ids=[uuid4()])

    async def drive(sd: Path) -> None:
        path = sd / "audit_events.jsonl"
        await asyncio.sleep(0.1)
        with path.open("a", encoding="utf-8") as f:
            f.write("{this is not valid json\n")
        await asyncio.sleep(0.15)
        _append_jsonl(path, good)

    events = await _collect(
        base_url,
        source_device_id=None,
        expected=2,
        drive=drive,
        storage_dir=storage_dir,
    )
    assert len(events) == 2

    by_type: dict[str, dict[str, Any]] = {t: p for t, p in events}
    assert "structlog_event" in by_type
    assert "audit_event" in by_type
    assert (
        by_type["structlog_event"]["payload"]["event"]
        == "audit_tail_malformed_line"
    )
    assert by_type["audit_event"]["payload"]["id"] == str(good.id)
