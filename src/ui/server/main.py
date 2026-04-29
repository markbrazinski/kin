"""FastAPI app for the KIN intake surface — 127.0.0.1 only.

Launch (dev):
    uvicorn ui.server.main:app --app-dir src --host 127.0.0.1 --port 8000

Why ``--app-dir src``: pyproject sets ``pythonpath = ["src"]`` so test/runtime
imports stay bare (``from core.x import y``); uvicorn needs the same path
prepend or the module fails to import.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI

from ui.server.routes import health, intake
from ui.server.structlog_config import configure_for_sse

log = structlog.get_logger(__name__)

DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage"


async def _warmup_ollama() -> None:
    """Fire-and-forget Ollama warmup so the first real ingest avoids
    cold-start latency. Failures are logged and tolerated; warmup is
    best-effort.

    Called from the app lifespan unless KIN_DISABLE_WARMUP=1 (used in
    tests to avoid an Ollama dependency).
    """
    try:
        import ollama
        from integration.ollama_adapter import OllamaAdapter

        log.info("pipeline_warmup_invoked")
        # OllamaAdapter wraps client.chat in asyncio.to_thread, so it
        # expects a sync ollama.Client (not AsyncClient).
        adapter = OllamaAdapter(client=ollama.Client())
        # Translate is the lowest-cost call surface; the result is
        # discarded. Ollama loads gemma4:e2b into memory on this
        # call, so the first real tool_call() avoids a 10-15s load.
        await adapter.translate(text="hello", source_lang="es")
        log.info("pipeline_warmup_complete")
    except Exception as exc:  # noqa: BLE001 — warmup is best-effort
        log.warning("pipeline_warmup_failed", error=str(exc))


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

        # Construct pipeline adapters once per app process so the
        # /intake/audio POST handler can reuse them without paying
        # per-request whisper-model-load cost. Behind KIN_DISABLE_WARMUP
        # so tests don't need a running Ollama or the whisper model
        # weights on disk.
        if os.environ.get("KIN_DISABLE_WARMUP") != "1":
            try:
                import ollama
                from faster_whisper import WhisperModel

                from integration.ollama_adapter import OllamaAdapter
                from integration.storage_adapter import StorageAdapter
                from integration.system_clock import SYSTEM_CLOCK
                from integration.whisper_adapter import WhisperAdapter

                whisper_model = WhisperModel(
                    "medium", device="cpu", compute_type="int8"
                )
                app.state.whisper = WhisperAdapter(
                    model=whisper_model, clock=SYSTEM_CLOCK
                )
                # Sync ollama.Client; OllamaAdapter wraps in to_thread.
                app.state.ollama = OllamaAdapter(client=ollama.Client())
                app.state.storage = StorageAdapter(
                    storage_dir=resolved_dir, clock=SYSTEM_CLOCK
                )
                log.info("pipeline_adapters_ready")
            except Exception as exc:  # noqa: BLE001 — adapter setup is best-effort
                log.warning("pipeline_adapters_unavailable", error=str(exc))
                app.state.whisper = None
                app.state.ollama = None
                app.state.storage = None
            asyncio.create_task(_warmup_ollama())
        else:
            app.state.whisper = None
            app.state.ollama = None
            app.state.storage = None
        yield

    app = FastAPI(title="kin", version="0.1.0", lifespan=lifespan)
    app.state.storage_dir = resolved_dir
    app.include_router(health.router)
    app.include_router(intake.router)

    # QA injection endpoint — only when KIN_QA_MODE=1. Used by Bundle 1
    # S4 manual smoke (QA-1). Off in production / default test runs.
    if os.environ.get("KIN_QA_MODE") == "1":
        from ui.server.routes import qa
        app.include_router(qa.router)
        log.info("qa_mode_enabled", endpoint="/qa/inject")

    return app


app = app_factory()
