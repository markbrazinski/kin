"""FastAPI app for the KIN intake surface — 127.0.0.1 only.

Launch (dev):
    uvicorn ui.server.main:app --app-dir src --host 127.0.0.1 --port 8000

Why ``--app-dir src``: pyproject sets ``pythonpath = ["src"]`` so test/runtime
imports stay bare (``from core.x import y``); uvicorn needs the same path
prepend or the module fails to import.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI

from ui.server.routes import health, intake
from ui.server.structlog_config import configure_for_sse

log = structlog.get_logger(__name__)

DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage"


def app_factory(storage_dir: Path | None = None) -> FastAPI:
    """Build a FastAPI app bound to a specific storage directory.

    Tests pass ``tmp_path``; the module-level ``app`` uses
    ``DEFAULT_STORAGE_DIR`` (repo-root /storage). Lifespan calls the
    structlog config so the SSE bridge processor is installed before
    any request arrives.
    """
    resolved_dir = storage_dir if storage_dir is not None else DEFAULT_STORAGE_DIR

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_for_sse()
        log.info("app_start", storage_dir=str(resolved_dir))
        yield

    app = FastAPI(title="kin", version="0.1.0", lifespan=lifespan)
    app.state.storage_dir = resolved_dir
    app.include_router(health.router)
    app.include_router(intake.router)
    return app


app = app_factory()
