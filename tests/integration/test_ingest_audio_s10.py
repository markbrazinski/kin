"""B2-S10 tests: multi-entity extraction for family roster + searcher.

Six tests covering the extended EXTRACT_INTAKE_FIELDS_TOOL schema,
FamilyMemberArg parsing, _map_extraction_to_intake roster population,
extend-path empty-roster preservation, and _to_rfl_record propagation.

Does NOT modify test_ingest_audio.py. The existing Carlos happy-path
test (test_ingest_audio_happy_path_spanish_carlos) serves as the
single-entity regression check and passes unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from core.rfl_schema import FamilyMember, RFLRecord
from core.storage_schemas import IntakeRecord
from core.tool_calling import ToolCallResult
from integration.extraction_tools import (
    EXTRACT_INTAKE_FIELDS_TOOL,
    ExtractIntakeFieldsArgs,
    FamilyMemberArg,
)
from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import (
    _map_extraction_to_intake,
    _to_rfl_record,
    ingest_audio,
)
from tests.fakes.fake_clock import FakeClock

# ─── Stubs (lifted from test_ingest_audio.py pattern) ─────────────


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


# ─── 1. Tool schema has all new properties ─────────────────────────


def test_extract_intake_fields_tool_schema_has_new_properties() -> None:
    """EXTRACT_INTAKE_FIELDS_TOOL declares all four S10 additions with
    correct types and nested items schema for family_members.
    """
    props = EXTRACT_INTAKE_FIELDS_TOOL["function"]["parameters"]["properties"]

    assert "searcher_name" in props
    assert props["searcher_name"]["type"] == ["string", "null"]

    assert "searcher_name_transliteration" in props
    assert props["searcher_name_transliteration"]["type"] == ["string", "null"]

    assert "searcher_relationship_to_target" in props
    assert props["searcher_relationship_to_target"]["type"] == ["string", "null"]

    assert "family_members" in props
    items = props["family_members"]["items"]
    assert items["type"] == "object"
    assert "name" in items["required"]
    assert "relationship_to_searcher" in items["required"]
    assert "name" in items["properties"]
    assert "age" in items["properties"]
    assert "status" in items["properties"]
    assert items["properties"]["status"]["enum"] == ["missing", "known", "present"]

    # Outer required stays empty — all fields optional.
    assert EXTRACT_INTAKE_FIELDS_TOOL["function"]["parameters"]["required"] == []


# ─── 2. ExtractIntakeFieldsArgs parses full multi-entity call ───────


def test_extract_intake_fields_args_parses_full_multi_entity_call() -> None:
    """Pydantic validates a full multi-entity tool-call payload:
    searcher identity + 2 roster members with varied field completeness.
    """
    raw: dict[str, Any] = {
        "full_name": "محمد",
        "relationship": "ابن",
        "age": 8,
        "searcher_name": "يوسف",
        "searcher_name_transliteration": "Yusuf",
        "searcher_relationship_to_target": "أب",
        "family_members": [
            {
                "name": "مريم",
                "name_transliteration": "Mariam",
                "relationship_to_searcher": "أخت",
                "status": "missing",
                "age": 32,
                "last_seen_location": "southern gate",
            },
            {
                "name": "محمود",
                "relationship_to_searcher": "ابن",
                "status": "missing",
            },
        ],
    }
    args = ExtractIntakeFieldsArgs(**raw)

    assert args.searcher_name == "يوسف"
    assert args.searcher_name_transliteration == "Yusuf"
    assert args.searcher_relationship_to_target == "أب"
    assert args.family_members is not None
    assert len(args.family_members) == 2

    m0 = args.family_members[0]
    assert isinstance(m0, FamilyMemberArg)
    assert m0.name == "مريم"
    assert m0.name_transliteration == "Mariam"
    assert m0.relationship_to_searcher == "أخت"
    assert m0.age == 32
    assert m0.last_seen_location == "southern gate"

    m1 = args.family_members[1]
    assert m1.name == "محمود"
    assert m1.age is None
    assert m1.name_transliteration is None


# ─── 3. _map_extraction_to_intake populates family_roster ──────────


def test_map_extraction_to_intake_populates_family_roster() -> None:
    """_map_extraction_to_intake maps FamilyMemberArg list to
    list[FamilyMember] and populates searcher_* fields correctly.
    """
    args = ExtractIntakeFieldsArgs(
        full_name="Carlos",
        relationship="hijo",
        searcher_name="Rosa",
        searcher_relationship_to_target="madre",
        family_members=[
            FamilyMemberArg(
                name="Lucia",
                relationship_to_searcher="hija",
                status="missing",
                age=6,
            ),
            FamilyMemberArg(
                name="Pedro",
                relationship_to_searcher="hijo",
                status="present",
            ),
        ],
    )

    fields = _map_extraction_to_intake(args, "es")

    roster = fields["family_roster"]
    assert isinstance(roster, list)
    assert len(roster) == 2

    lucia = roster[0]
    assert isinstance(lucia, FamilyMember)
    assert lucia.name == "Lucia"
    assert lucia.relationship_to_searcher == "hija"
    assert lucia.status == "missing"
    assert lucia.age == 6

    pedro = roster[1]
    assert pedro.name == "Pedro"
    assert pedro.status == "present"

    assert fields["searcher_name"] == "Rosa"
    assert fields["searcher_relationship_to_target"] == "madre"
    assert fields["searcher_name_transliteration"] == ""


# ─── 4. _map_extraction_to_intake returns [] when family_members absent


def test_map_extraction_to_intake_empty_roster_when_family_members_absent() -> None:
    """When family_members is None (field omitted by model), family_roster
    is [] — not None, not a missing key. Preserves backward compat for
    single-entity tool calls.
    """
    args = ExtractIntakeFieldsArgs(
        full_name="Carlos",
        relationship="hijo",
    )
    assert args.family_members is None

    fields = _map_extraction_to_intake(args, "es")

    assert "family_roster" in fields
    assert fields["family_roster"] == []
    assert isinstance(fields["family_roster"], list)


# ─── 5. (Regression) Carlos test in test_ingest_audio.py passes as-is.
#    No new code needed here — the existing test file covers it.


# ─── 6. Extend path preserves roster when turn-2 omits family_members ─


@pytest.mark.asyncio
async def test_extend_path_preserves_populated_roster_on_empty_turn(
    tmp_path: Path,
) -> None:
    """A populated roster from turn 1 survives a turn-2 tool call that
    returns no family_members. Exercises the `v != []` guard in the
    extend-path filter.
    """
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    # Turn 1: name + relationship + 2 roster members.
    turn1_ollama = _OllamaStub(
        english="I am looking for my son Carlos and can tell you about my family.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "Carlos",
                "relationship": "hijo",
                "family_members": [
                    {
                        "name": "Lucia",
                        "relationship_to_searcher": "hija",
                        "status": "missing",
                    },
                    {
                        "name": "Pedro",
                        "relationship_to_searcher": "hijo",
                        "status": "present",
                    },
                ],
            },
        ),
    )
    record1, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Estoy buscando a mi hijo Carlos..."),
        ollama=turn1_ollama,
        storage=storage,
    )
    assert len(record1.family_roster) == 2

    # Turn 2: adds age only; family_members absent → maps to [] → filter drops it.
    turn2_ollama = _OllamaStub(
        english="He is 8 years old.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"age": 8},
        ),
    )
    record2, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Tiene 8 años."),
        ollama=turn2_ollama,
        storage=storage,
        intake_id=record1.id,
    )

    assert record2.id == record1.id
    assert record2.age == 8
    assert len(record2.family_roster) == 2
    assert record2.family_roster[0].name == "Lucia"
    assert record2.family_roster[1].name == "Pedro"


# ─── 7. _to_rfl_record maps family_roster + searcher into RFLRecord ─


def test_to_rfl_record_maps_family_roster_and_searcher_fields() -> None:
    """_to_rfl_record propagates family_roster and searcher_* fields
    from IntakeRecord into the returned RFLRecord.
    """
    now = datetime.now(UTC)
    intake = IntakeRecord(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        status="partial",
        language="ar",
        source_device_id="tent_a",
        full_name_source_script="محمد",
        full_name_transliteration="",
        relationship_to_seeker="ابن",
        searcher_name="يوسف",
        searcher_name_transliteration="Yusuf",
        searcher_relationship_to_target="أب",
        family_roster=[
            FamilyMember(
                name="مريم",
                name_transliteration="Mariam",
                relationship_to_searcher="أخت",
                status="missing",
                age=32,
            ),
        ],
    )

    rfl = _to_rfl_record(intake)

    assert isinstance(rfl, RFLRecord)
    assert rfl.searcher_name == "يوسف"
    assert rfl.searcher_name_transliteration == "Yusuf"
    assert rfl.searcher_relationship_to_target == "أب"
    assert len(rfl.family_roster) == 1
    assert rfl.family_roster[0].name == "مريم"
    assert rfl.family_roster[0].name_transliteration == "Mariam"
    assert rfl.family_roster[0].age == 32
