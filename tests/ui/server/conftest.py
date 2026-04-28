"""Test fixtures for /intake/stream — runs a real uvicorn on an
ephemeral port per test, because httpx.ASGITransport buffers the
whole response and deadlocks on open-ended SSE streams.
"""
from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
import uvicorn

from ui.server.main import app_factory


def _free_port() -> int:
    """Bind a socket to port 0, read back the OS-assigned port, release."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _UvicornInThread:
    """Run a uvicorn server in a daemon thread. Yields once the
    server's startup has completed; teardown asks for graceful exit
    and joins.
    """

    def __init__(self, app_obj: object, port: int) -> None:
        config = uvicorn.Config(
            app=app_obj,  # type: ignore[arg-type]
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
            loop="asyncio",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run, name="uvicorn-test", daemon=True
        )

    async def start(self) -> None:
        self.thread.start()
        # Poll until the server flips its started flag (uvicorn sets
        # this after lifespan startup completes).
        for _ in range(200):
            if self.server.started:
                return
            await asyncio.sleep(0.025)
        raise RuntimeError("uvicorn did not start within 5s")

    async def stop(self) -> None:
        self.server.should_exit = True
        for _ in range(200):
            if not self.thread.is_alive():
                return
            await asyncio.sleep(0.025)
        # Daemon thread; if it didn't exit cleanly the process tear-down
        # will handle it. Don't block the test session.


@pytest_asyncio.fixture
async def sse_server(tmp_path: Path) -> AsyncIterator[tuple[str, Path]]:
    """Start a uvicorn server bound to ``tmp_path`` storage.

    Yields ``(base_url, tmp_path)``. The base_url is what tests pass
    to httpx.AsyncClient.
    """
    port = _free_port()
    app = app_factory(tmp_path)
    runner = _UvicornInThread(app, port)
    await runner.start()
    try:
        yield f"http://127.0.0.1:{port}", tmp_path
    finally:
        await runner.stop()
