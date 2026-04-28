"""FastAPI app for the KIN intake surface — 127.0.0.1 only.

Launch (dev):
    uvicorn ui.server.main:app --app-dir src --host 127.0.0.1 --port 8000

Why ``--app-dir src``: pyproject sets ``pythonpath = ["src"]`` so test/runtime
imports stay bare (``from core.x import y``); uvicorn needs the same path
prepend or the module fails to import.
"""
from __future__ import annotations

import structlog
from fastapi import FastAPI

from ui.server.routes import health, intake

log = structlog.get_logger(__name__)

app = FastAPI(title="kin", version="0.1.0")
app.include_router(health.router)
app.include_router(intake.router)

log.info("app_start")
