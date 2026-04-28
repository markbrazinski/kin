"""Merged SSE stream — audit_events.jsonl tail + in-process structlog queue.

Single async generator drains both sources and yields a tagged envelope
per event. Each event has a ``type`` discriminator (``audit_event`` or
``structlog_event``) and an optional ``source_device_id`` for client-side
filtering. Filter applies server-side when the query param is set:
audit events without a known device-id mapping are dropped under an
active filter; structlog events are dropped only if they carry a
``source_device_id`` field that doesn't match.

No history replay on reconnect (Bundle 1 decision #4) — tail seeks to
end-of-file at open. Default sse-starlette ping (~15s) handles keepalive.

Single-writer JSONL guarantees ``intake_created`` flushes before any
downstream ``field_extracted`` on the same record_id; unmapped record_ids
under an active source_device_id filter are dropped intentionally
(see Bundle 1 S1 plan, Resolution B).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict

from core.storage_schemas import AuditEvent, IntakeRecord
from integration.storage_adapter import AUDIT_FILE, INTAKE_FILE

log = structlog.get_logger(__name__)

EventKind = Literal["audit_event", "structlog_event"]

_TAIL_POLL_SECONDS = 0.05
_STRUCTLOG_QUEUE_MAXSIZE = 256


# ─── Envelope ─────────────────────────────────────────────────────


class EventEnvelope(BaseModel):
    """Wire shape for a single SSE event.

    ``payload`` carries the underlying record (AuditEvent dump or
    structlog event_dict) verbatim; ``source_device_id`` is the
    server-side join result, may be None for events the server
    cannot attribute to a device.
    """

    model_config = ConfigDict(extra="ignore")

    type: EventKind
    at: datetime
    source_device_id: str | None = None
    payload: dict[str, Any]


# ─── Structlog → SSE bridge (process-wide registry) ───────────────

_active_structlog_queues: set[asyncio.Queue[dict[str, Any]]] = set()


def register_structlog_queue(q: asyncio.Queue[dict[str, Any]]) -> None:
    _active_structlog_queues.add(q)


def unregister_structlog_queue(q: asyncio.Queue[dict[str, Any]]) -> None:
    _active_structlog_queues.discard(q)


def structlog_sse_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: push a copy of every event to every active queue.

    Non-blocking: if a queue is full, drop the event for that consumer
    rather than block the logging call. Returns event_dict unchanged so
    other processors / renderers downstream still run.
    """
    if _active_structlog_queues:
        snapshot = dict(event_dict)
        for q in tuple(_active_structlog_queues):
            try:
                q.put_nowait(snapshot)
            except asyncio.QueueFull:
                pass
    return event_dict


# ─── Audit-event tail ─────────────────────────────────────────────


def _read_new_lines(handle: Any) -> list[str]:
    """Blocking read of any newly-appended complete lines."""
    lines: list[str] = []
    while True:
        line = handle.readline()
        if not line:
            break
        if line.endswith("\n"):
            lines.append(line.rstrip("\n"))
        else:
            # Partial line (write in progress); rewind to before it and stop.
            handle.seek(handle.tell() - len(line))
            break
    return lines


async def _audit_tail(audit_path: Path) -> AsyncIterator[AuditEvent]:
    """tail -f equivalent over a JSONL file, yielding parsed AuditEvents.

    If the file exists at connect time, seek to end-of-file (no history
    replay, per Bundle 1 decision #4). If the file doesn't yet exist at
    connect, poll for it and then read from byte 0 — those lines are
    not "history" relative to this connection; they're the first events
    written *after* the consumer attached.
    """
    pre_existing = audit_path.exists()
    while not audit_path.exists():
        await asyncio.sleep(_TAIL_POLL_SECONDS)

    handle = audit_path.open("r", encoding="utf-8")
    try:
        if pre_existing:
            handle.seek(0, 2)  # end of file
        while True:
            lines = await asyncio.to_thread(_read_new_lines, handle)
            if not lines:
                await asyncio.sleep(_TAIL_POLL_SECONDS)
                continue
            for raw in lines:
                if not raw.strip():
                    continue
                try:
                    yield AuditEvent.model_validate_json(raw)
                except Exception as exc:
                    log.warning(
                        "audit_tail_malformed_line",
                        path=str(audit_path),
                        error=str(exc),
                    )
                    continue
    finally:
        handle.close()


# ─── Device-id cache ──────────────────────────────────────────────


def _seed_device_cache(intake_path: Path) -> dict[UUID, str]:
    """One-time read of intake_records.jsonl into a record_id → device map."""
    cache: dict[UUID, str] = {}
    if not intake_path.exists():
        return cache
    with intake_path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = IntakeRecord.model_validate_json(raw)
            except Exception as exc:
                log.warning(
                    "intake_seed_malformed_line",
                    path=str(intake_path),
                    error=str(exc),
                )
                continue
            cache[rec.id] = rec.source_device_id
    return cache


def _device_id_for_audit(
    event: AuditEvent,
    cache: dict[UUID, str],
    intake_path: Path,
) -> str | None:
    """Resolve a device_id for an audit event; refresh cache on miss."""
    for rid in event.record_ids:
        if rid in cache:
            return cache[rid]
    # Cache miss — refresh once. Single-writer JSONL means an
    # intake_created flush precedes any downstream field_extracted on
    # the same record_id, so a refresh here is sufficient.
    cache.update(_seed_device_cache(intake_path))
    for rid in event.record_ids:
        if rid in cache:
            return cache[rid]
    return None


# ─── Merged stream ────────────────────────────────────────────────


async def merged_stream(
    *,
    storage_dir: Path,
    source_device_id: str | None,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE-shaped dicts (``{"event": ..., "data": ...}``) from the
    merged source until the consumer disconnects.

    sse-starlette accepts dicts of this shape and handles framing.
    """
    audit_path = storage_dir / AUDIT_FILE
    intake_path = storage_dir / INTAKE_FILE

    device_cache: dict[UUID, str] = _seed_device_cache(intake_path)

    structlog_q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
        maxsize=_STRUCTLOG_QUEUE_MAXSIZE
    )
    register_structlog_queue(structlog_q)

    audit_iter = _audit_tail(audit_path)
    audit_task: asyncio.Task[AuditEvent] | None = None
    structlog_task: asyncio.Task[dict[str, Any]] | None = None

    try:
        # Flush headers immediately so the consumer's connect resolves
        # before any real event arrives. sse-starlette renders the
        # ``comment`` key as an SSE comment line (``: ...``) which the
        # EventSource API ignores.
        yield {"comment": "stream-open"}
        while True:
            if audit_task is None:
                audit_task = asyncio.create_task(audit_iter.__anext__())
            if structlog_task is None:
                structlog_task = asyncio.create_task(structlog_q.get())

            done, _pending = await asyncio.wait(
                {audit_task, structlog_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for finished in done:
                if finished is audit_task:
                    try:
                        event: AuditEvent = finished.result()
                    except StopAsyncIteration:
                        audit_task = None
                        continue
                    audit_task = None

                    device_id = _device_id_for_audit(
                        event, device_cache, intake_path
                    )
                    if (
                        source_device_id is not None
                        and device_id != source_device_id
                    ):
                        # Drop intentionally: under an active filter we
                        # can't prove this event belongs to the queried
                        # device. Two-record match events pass if either
                        # record_id resolves to the queried device.
                        if event.record_ids:
                            matched = False
                            for rid in event.record_ids:
                                if (
                                    device_cache.get(rid)
                                    == source_device_id
                                ):
                                    matched = True
                                    break
                            if not matched:
                                continue
                        else:
                            continue
                    envelope = EventEnvelope(
                        type="audit_event",
                        at=event.at,
                        source_device_id=device_id,
                        payload=json.loads(event.model_dump_json()),
                    )
                    yield {
                        "event": "audit_event",
                        "data": envelope.model_dump_json(),
                    }
                elif finished is structlog_task:
                    record: dict[str, Any] = finished.result()
                    structlog_task = None

                    record_device = record.get("source_device_id")
                    if (
                        source_device_id is not None
                        and record_device is not None
                        and record_device != source_device_id
                    ):
                        continue
                    envelope = EventEnvelope(
                        type="structlog_event",
                        at=_extract_structlog_timestamp(record),
                        source_device_id=(
                            record_device
                            if isinstance(record_device, str)
                            else None
                        ),
                        payload=_jsonable_record(record),
                    )
                    yield {
                        "event": "structlog_event",
                        "data": envelope.model_dump_json(),
                    }
    finally:
        unregister_structlog_queue(structlog_q)
        # Cancel and await pending tasks before aclose'ing the audit
        # generator: aclose() raises RuntimeError if a coroutine is
        # still suspended inside the generator's frame.
        for task in (audit_task, structlog_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass
                except Exception:
                    pass
        try:
            await audit_iter.aclose()
        except Exception:
            pass


# ─── Helpers ──────────────────────────────────────────────────────


def _extract_structlog_timestamp(record: dict[str, Any]) -> datetime:
    """Pull a datetime from the structlog record, fallback to now()."""
    ts = record.get("timestamp")
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            pass
    return datetime.now()


def _jsonable_record(record: dict[str, Any]) -> dict[str, Any]:
    """Coerce a structlog event_dict to a JSON-serializable shape."""
    out: dict[str, Any] = {}
    for k, v in record.items():
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = repr(v)
    return out
