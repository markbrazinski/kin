"""Pydantic schema for OllamaAdapter.tool_call() return type.

Kept separate from storage_schemas.py because tool-calling is a
distinct concern (Integration-layer return shape, not a persisted
record). See integration/ollama_adapter.tool_call().
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCallResult(BaseModel):
    """Structured tool-call response from a single ollama.chat invocation.

    arguments is the raw, already-parsed dict from the SDK
    (response.message.tool_calls[0].function.arguments). Caller is
    responsible for validating arguments against any tool-specific
    Pydantic model — e.g. ExtractIntakeFieldsArgs in
    integration/extraction_tools.py.

    extra='forbid' so callers can't sneak unintended fields onto the
    return type; tool_call() should only ever populate name + arguments.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any]
