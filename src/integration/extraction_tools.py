"""Module-level constants for the extract_intake_fields tool.

EXTRACT_INTAKE_FIELDS_TOOL is the JSON Schema dict passed to
OllamaAdapter.tool_call(); lifted verbatim from the Apr 28 GREEN
hello-world (scripts/gemma_extraction_helloworld.py) and validated
across EN/AR/FA in the Apr 29 multilang sweep
(scripts/gemma_extraction_multilang_sweep.py).

ExtractIntakeFieldsArgs is the Pydantic model S4 uses to validate the
arguments dict returned by tool_call(). tool_call() itself does NOT
validate against this model — keeps the adapter reusable for future
tools.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


EXTRACT_INTAKE_FIELDS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "extract_intake_fields",
        "description": (
            "Extract intake fields about a missing person from the speaker's "
            "statement."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {
                    "type": "string",
                    "description": "Full name of the missing person.",
                },
                "relationship": {
                    "type": "string",
                    "description": (
                        "Speaker's relationship to the missing person "
                        "(e.g., 'son', 'daughter', 'hijo', 'hija', "
                        "'ابن', 'پسر')."
                    ),
                },
                "age": {
                    "type": ["integer", "null"],
                    "description": (
                        "Age of the missing person if stated; null if not stated."
                    ),
                },
            },
            "required": ["full_name", "relationship"],
        },
    },
}


class ExtractIntakeFieldsArgs(BaseModel):
    """Validates raw arguments dict from extract_intake_fields tool calls.

    Used by S4 ingest_audio() to validate ToolCallResult.arguments
    before mapping to IntakeRecord fields per the discrepancy #3
    rule: full_name → full_name_source_script (always) and
    full_name_transliteration (only for Latin-script source langs).

    extra='ignore' so future tool-schema additions don't break
    consumers that still validate against the older shape.
    """

    model_config = ConfigDict(extra="ignore")

    full_name: str
    relationship: str
    age: int | None = None
