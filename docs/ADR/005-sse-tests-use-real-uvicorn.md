# ADR-005: SSE route tests use real uvicorn, not httpx ASGITransport

**Status:** Accepted
**Date:** [today]
**Context:** Bundle 1 S1 (commit db200eb)

## Decision

SSE-route tests use the `sse_server` pytest fixture (real uvicorn-in-thread on an ephemeral port) and connect via standard `httpx.AsyncClient` against the bound port. They do NOT use `httpx.ASGITransport`.

## Context

S1 implemented the `/intake/stream` SSE endpoint with an open-ended async generator (`merged_stream`). Initial test attempts using `httpx.ASGITransport + AsyncClient + aconnect_sse` (the pattern inherited from the Phase-1 stub tests at `tests/ui/server/test_routes.py`) hung indefinitely.

Root cause: `httpx.ASGITransport` (`asgi.py:170-181`) buffers the entire ASGI response in memory and only resolves the `Response` object when the app's `__call__` returns. For a finite stub stream that emits N events and closes, this works. For an open-ended SSE stream, `__call__` only returns when the client disconnects — but the client cannot disconnect until it has a `Response` object. Deadlock.

The Phase-1 stub tests passed because the stub stream was finite (5 events then close). The S1 merged stream is open-ended by design.

## Decision detail

`tests/ui/server/conftest.py` ships an `sse_server` fixture that:
- Starts uvicorn on `127.0.0.1:0` (ephemeral port) in a daemon thread
- Reads the actual bound port back from the server
- Yields the `http://127.0.0.1:{port}` base URL to tests
- Tears down the server on fixture exit

Tests then use a normal `httpx.AsyncClient` with `httpx_sse.aconnect_sse` against the real HTTP port. The harness exercises the same code path uvicorn runs in production.

## Alternatives considered

**Make the stream finite-by-test-param.** Add `?max_events=N` to terminate the stream for tests. Rejected: production code shaped by test convenience; the param has no use in the actual demo and would be visible to a code-reading judge.

**`asgi-lifespan` + streaming-aware ASGI harness.** Rejected: introduces a new dep with edge cases vs uvicorn's behavior; uvicorn-in-thread is the same machinery production runs.

## Constraints for future SSE-touching sessions

- Any new SSE route test MUST use the `sse_server` fixture, not `ASGITransport`
- The fixture is session-scoped; per-test isolation happens at the storage layer (each test passes its own `tmp_path` storage dir to the server)
- Subprocess vs thread: thread chosen for simplicity; if structlog config pollution surfaces in future sessions, escalate to subprocess

## Consequences

Positive: tests exercise real HTTP framing; ASGI streaming gotchas surface here, not at recording time.
Negative: ~70 lines of fixture code; slightly slower test boot than ASGITransport (one-time, session-scoped, negligible).

## References

- httpx ASGITransport source: `asgi.py:170-181`
- Fixture: `tests/ui/server/conftest.py`
- First user: `tests/ui/server/test_sse.py`