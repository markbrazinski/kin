"""Health probe — returns 200 to prove the FastAPI app is reachable."""
from __future__ import annotations

import structlog
from fastapi import APIRouter

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    log.info("healthz_ping")
    return {"status": "ok"}
