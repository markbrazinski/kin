"""Schema tests for ToolCallResult — round-trip + extra-field rejection."""

import pytest
from pydantic import ValidationError

from core.tool_calling import ToolCallResult


def test_tool_call_result_round_trip() -> None:
    """A populated ToolCallResult round-trips through model_dump_json /
    model_validate_json without loss.
    """
    result = ToolCallResult(
        name="extract_intake_fields",
        arguments={"full_name": "Carlos", "relationship": "son", "age": 8},
    )
    rt = ToolCallResult.model_validate_json(result.model_dump_json())
    assert rt == result


def test_tool_call_result_rejects_extra_fields() -> None:
    """ConfigDict(extra='forbid') prevents callers from sneaking
    unintended fields onto the return type.
    """
    with pytest.raises(ValidationError):
        ToolCallResult.model_validate(
            {
                "name": "extract_intake_fields",
                "arguments": {"full_name": "Carlos"},
                "garbage": "should not be allowed",
            }
        )
