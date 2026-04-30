"""S5 extend-path tests for ingest_audio + matching re-trigger.

S4's ingest_audio always created. S5 adds the ``intake_id`` keyword
parameter so a second/third turn merges its extracted fields into an
existing record. Crisis branch is create-only; extending into a
crisis turn raises ValueError.

Six tests cover:
1. Extend path merges fields across two turns
2. Extend path on unknown intake_id raises KeyError
3. Extend into crisis turn raises ValueError
4. distinguishing_features round-trips through Pydantic + JSON Schema
5. _maybe_retrigger_matching fires on identity-bearing field change
6. _maybe_retrigger_matching skips on non-identity field change
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from core.tool_calling import ToolCallResult
from integration.extraction_tools import (
    EXTRACT_INTAKE_FIELDS_TOOL,
    ExtractIntakeFieldsArgs,
)
from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import (
    _maybe_retrigger_matching,
    ingest_audio,
)
from tests.fakes.fake_clock import FakeClock


# ─── Stubs (lifted from test_ingest_audio.py) ─────────────────────


class _WhisperStub:
    def __init__(self, text: str = "hola") -> None:
        self._text = text

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        return self._text


class _OllamaStub:
    def __init__(
        self,
        english: str = "hello",
        tool_call_response: ToolCallResult | None = None,
    ) -> None:
        self._english = english
        self._tool_call_response = tool_call_response

    async def translate(self, text: str, source_lang: str) -> str:
        return self._english

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult:
        if self._tool_call_response is None:
            raise AssertionError(
                "_OllamaStub.tool_call invoked without configured response"
            )
        return self._tool_call_response


def _adapter(tmp_path: Path) -> StorageAdapter:
    return StorageAdapter(tmp_path / "storage", FakeClock())


def _audio(tmp_path: Path) -> Path:
    p = tmp_path / "clip.wav"
    p.write_bytes(b"")
    return p


# ─── 1. Extend merges fields across two turns ─────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_extend_path_merges_fields(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    # Turn 1: name + relationship.
    turn1_ollama = _OllamaStub(
        english="I'm looking for my son Carlos.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )
    record1, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Estoy buscando a mi hijo Carlos."),
        ollama=turn1_ollama,
        storage=storage,
    )
    assert record1.full_name_source_script == "Carlos"
    assert record1.relationship_to_seeker == "hijo"
    assert record1.age is None

    # Turn 2: extend with age + distinguishing features.
    turn2_ollama = _OllamaStub(
        english="He is 8 years old. He has a scar on his cheek.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "Carlos",
                "relationship": "hijo",
                "age": 8,
                "distinguishing_features": "scar on cheek",
            },
        ),
    )
    record2, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Tiene 8 años. Tiene una cicatriz."),
        ollama=turn2_ollama,
        storage=storage,
        intake_id=record1.id,
    )

    # Same record id (extend, not create).
    assert record2.id == record1.id
    # Turn 1 fields survived.
    assert record2.full_name_source_script == "Carlos"
    assert record2.relationship_to_seeker == "hijo"
    # Turn 2 fields landed.
    assert record2.age == 8
    assert record2.is_minor is True
    assert record2.distinguishing_marks == "scar on cheek"
    # Status promoted to complete (both required fields present).
    assert record2.status == "complete"


# ─── 2. Extend on unknown intake_id raises KeyError ───────────────


@pytest.mark.asyncio
async def test_ingest_audio_extend_raises_on_unknown_intake_id(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    bogus_id = uuid4()
    ollama = _OllamaStub(
        english="hello",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )

    with pytest.raises(KeyError, match=str(bogus_id)):
        await ingest_audio(
            audio,
            "es",
            "tent_a",
            whisper=_WhisperStub("hola"),
            ollama=ollama,
            storage=storage,
            intake_id=bogus_id,
        )


# ─── 3. Extend into crisis turn raises ValueError ─────────────────


@pytest.mark.asyncio
async def test_ingest_audio_extend_raises_on_crisis_branch(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    # Create a normal record first.
    create_ollama = _OllamaStub(
        english="hello",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )
    record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Estoy buscando a Carlos."),
        ollama=create_ollama,
        storage=storage,
    )

    # Now try to extend with a crisis-keyword utterance.
    extend_ollama = _OllamaStub(english="kill me now", tool_call_response=None)

    with pytest.raises(ValueError, match="crisis path is create-only"):
        await ingest_audio(
            audio,
            "ar",
            "tent_a",
            whisper=_WhisperStub("اقتلني الآن"),
            ollama=extend_ollama,
            storage=storage,
            intake_id=record.id,
        )


# ─── 4. distinguishing_features schema round-trip ─────────────────


def test_extract_intake_fields_distinguishing_features_round_trip() -> None:
    """Pydantic accepts the new field; JSON schema declares it."""
    args = ExtractIntakeFieldsArgs(
        full_name="Mohammed",
        relationship="hijo",
        age=10,
        distinguishing_features="scar on left cheek",
    )
    assert args.distinguishing_features == "scar on left cheek"

    # Optional / default None when omitted.
    args_no_feat = ExtractIntakeFieldsArgs(
        full_name="Carlos", relationship="hijo"
    )
    assert args_no_feat.distinguishing_features is None

    # JSON Schema declares it under properties (string|null).
    properties = EXTRACT_INTAKE_FIELDS_TOOL["function"]["parameters"][
        "properties"
    ]
    assert "distinguishing_features" in properties
    assert "string" in properties["distinguishing_features"]["type"]


# ─── 5. _maybe_retrigger_matching fires on identity field ─────────


@pytest.mark.asyncio
async def test_maybe_retrigger_matching_fires_on_identity_field(
    tmp_path: Path,
) -> None:
    """Pre-seed two records that should match by source-script name +
    age. Update one record's transliteration; the helper must fire
    matching and produce a MatchLink.
    """
    storage = _adapter(tmp_path)

    # Pre-seed Tent A (Mohammed in Latin script — pretend it was a
    # Latin-script intake; matching is purely about the canonical name
    # plus corroborating fields).
    rec_a = storage.create_intake_record(
        language="en",
        source_device_id="tent_a",
    )
    rec_a = storage.update_intake_record(
        rec_a.id,
        full_name_source_script="Mohammed",
        full_name_transliteration="Mohammed",
        relationship_to_seeker="son",
        age=10,
    )

    # Pre-seed Tent B (Arabic source script with empty transliteration).
    rec_b = storage.create_intake_record(
        language="ar",
        source_device_id="tent_b",
    )
    rec_b = storage.update_intake_record(
        rec_b.id,
        full_name_source_script="محمد",
        full_name_transliteration="",
        relationship_to_seeker="ابن",
        age=10,
    )

    # Now simulate the worker entering "Mohammed" as Tent B's
    # transliteration. Update via storage and call the helper.
    rec_b = storage.update_intake_record(
        rec_b.id, full_name_transliteration="Mohammed"
    )
    matches = await _maybe_retrigger_matching(
        rec_b,
        changed_fields={"full_name_transliteration"},
        storage=storage,
    )

    # Helper returned at least one MatchLink (against Tent A).
    assert len(matches) >= 1
    other_ids = {m.record_a_id for m in matches} | {
        m.record_b_id for m in matches
    }
    assert rec_a.id in other_ids


# ─── 6. _maybe_retrigger_matching skips on non-identity field ─────


@pytest.mark.asyncio
async def test_maybe_retrigger_matching_skips_on_non_identity_field(
    tmp_path: Path,
) -> None:
    """Updating ``referral_organization`` is not identity-bearing; the
    helper must return [] and not run matching.
    """
    storage = _adapter(tmp_path)

    rec = storage.create_intake_record(
        language="es", source_device_id="tent_a"
    )
    rec = storage.update_intake_record(
        rec.id,
        full_name_source_script="Carlos",
        full_name_transliteration="Carlos",
        relationship_to_seeker="hijo",
    )

    matches = await _maybe_retrigger_matching(
        rec,
        changed_fields={"referral_organization"},
        storage=storage,
    )
    assert matches == []
