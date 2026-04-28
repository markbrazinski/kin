"""Process-wide structlog configuration with the SSE bridge processor.

Idempotent: safe to call multiple times in tests. Installs the SSE
fanout processor early in the chain so every emitted event is mirrored
to active per-connection queues before it's rendered for stdout.
"""
from __future__ import annotations

import structlog

from ui.server.sse import structlog_sse_processor

_configured = False


def configure_for_sse() -> None:
    """Install the SSE fanout processor + a JSON renderer for stdout.

    Idempotent. Subsequent calls are no-ops; this matters for tests
    that build many app instances in the same process.
    """
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog_sse_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=True,
    )
    _configured = True
