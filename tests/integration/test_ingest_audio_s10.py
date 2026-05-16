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
    _detect_present_status,
    _ensure_primary_in_roster,
    _extract_member_ages,
    _fill_transliterations,
    _map_extraction_to_intake,
    _promote_first_missing_to_primary,
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


# ─── 5a. Searcher age preserved through promotion; record.age = primary's age


def test_promote_does_not_clobber_searcher_age_and_map_uses_primary() -> None:
    """args.age per the tool schema is the SEARCHER's age. The previous
    _promote_first_missing_to_primary implementation overwrote args.age
    with the promoted member's age, destroying the searcher's age.

    After the fix:
      - _promote_first_missing_to_primary leaves args.age intact.
      - _map_extraction_to_intake sources record.age from the primary
        member's family_members entry, NOT from args.age.
      - is_minor uses args.age for the searcher check; here both are
        adults so is_minor is False.
    """
    args = ExtractIntakeFieldsArgs(
        age=41,                                 # searcher's age
        searcher_name="Yusuf",
        family_members=[
            FamilyMemberArg(
                name="Mariam",
                relationship_to_searcher="sister",
                status="missing",
                age=32,
            ),
        ],
    )

    promoted = _promote_first_missing_to_primary(args)
    # Promotion fills full_name from the first missing member.
    assert promoted.full_name == "Mariam"
    # Critical: args.age is preserved (NOT overwritten with Mariam's 32).
    assert promoted.age == 41

    fields = _map_extraction_to_intake(promoted, "en")
    # record.age is the PRIMARY missing person's age (Mariam = 32),
    # NOT the searcher's age (41).
    assert fields["age"] == 32
    # is_minor: searcher (41) not minor; primary (Mariam, 32) not minor → False.
    assert fields["is_minor"] is False


# ─── 5b. Member-minor flag fires from family member, not searcher ─────


def test_member_minor_flag_independent_of_searcher_age() -> None:
    """is_minor must fire when any missing family member is under 18,
    regardless of the searcher's age. After the fix, args.age stays as
    the searcher's age, so the searcher_minor check works correctly:
    adult searcher with a child in the roster still flags is_minor.
    """
    args = ExtractIntakeFieldsArgs(
        age=41,                                 # adult searcher
        searcher_name="Yusuf",
        family_members=[
            FamilyMemberArg(
                name="Mohammed",
                relationship_to_searcher="nephew",
                status="missing",
                age=8,                          # minor missing child
            ),
        ],
    )

    promoted = _promote_first_missing_to_primary(args)
    assert promoted.full_name == "Mohammed"
    assert promoted.age == 41                   # searcher's age preserved

    fields = _map_extraction_to_intake(promoted, "en")
    # record.age = primary missing person's age (Mohammed = 8).
    assert fields["age"] == 8
    # is_minor True because Mohammed (missing, 8) trips member_minor —
    # NOT because the searcher is a minor (searcher is 41).
    assert fields["is_minor"] is True


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
    # _ensure_primary_in_roster prepends Carlos → 3 entries total.
    assert len(record1.family_roster) == 3
    assert record1.family_roster[0].name == "Carlos"
    assert record1.family_roster[1].name == "Lucia"
    assert record1.family_roster[2].name == "Pedro"

    # Turn 2: adds age only; family_members absent → maps to [] → filter drops it.
    # Per the tool schema, top-level args.age is the SEARCHER's age — and
    # record.age (the primary missing person's age) is now sourced from
    # family_members[primary] in _map_extraction_to_intake. With no
    # family_members on this turn, primary_age is None and the extend
    # filter drops it. record2.age stays at its turn-1 value (None).
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
    # Full 3-entry roster survives the extend turn.
    assert len(record2.family_roster) == 3
    assert record2.family_roster[0].name == "Carlos"
    assert record2.family_roster[1].name == "Lucia"
    assert record2.family_roster[2].name == "Pedro"


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


# ─── 8. _ensure_primary_in_roster prepends primary when absent ──────


def test_ensure_primary_in_roster_prepends_when_absent() -> None:
    """When full_name is not in family_members, it is prepended at index 0."""
    args = ExtractIntakeFieldsArgs(
        full_name="يوسف",
        relationship="أخ",
        age=41,
        family_members=[
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن", age=8),
        ],
    )
    result = _ensure_primary_in_roster(args)

    assert result.family_members is not None
    assert len(result.family_members) == 2
    assert result.family_members[0].name == "يوسف"
    assert result.family_members[0].relationship_to_searcher == "أخ"
    assert result.family_members[0].status == "missing"
    assert result.family_members[0].age == 41
    assert result.family_members[1].name == "محمد"


# ─── 9. _ensure_primary_in_roster is idempotent when primary present ─


def test_ensure_primary_in_roster_idempotent_when_already_present() -> None:
    """When full_name is already in family_members, no duplication occurs."""
    args = ExtractIntakeFieldsArgs(
        full_name="يوسف",
        relationship="أخ",
        family_members=[
            FamilyMemberArg(name="يوسف", relationship_to_searcher="أخ", status="missing"),
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن", status="missing"),
        ],
    )
    result = _ensure_primary_in_roster(args)

    assert result.family_members is not None
    assert len(result.family_members) == 2
    names = [m.name for m in result.family_members]
    assert names.count("يوسف") == 1


# ─── 10. Mariam Arabic intake: both Yusuf and Mohamad in roster ─────


@pytest.mark.asyncio
async def test_mariam_arabic_two_missing_persons_both_in_roster(
    tmp_path: Path,
) -> None:
    """Regression guard for the Mariam demo bug: Gemma puts Yusuf in
    full_name only and Mohamad in family_members only. After
    _ensure_primary_in_roster, both appear in family_roster.
    """
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    ollama = _OllamaStub(
        english=(
            "I am Mariam. I am looking for my brother Yusuf "
            "and my son Mohamad, age 8."
        ),
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "يوسف",
                "relationship": "أخ",
                "searcher_name": "مريم",
                "searcher_relationship_to_target": "أخت",
                "last_seen_location": "البوابة الجنوبية",
                "last_seen_date": "قبل ثلاثة أيام",
                "family_members": [
                    {
                        "name": "محمد",
                        "relationship_to_searcher": "ابن",
                        "status": "missing",
                        "age": 8,
                    }
                ],
            },
        ),
    )

    record, _ = await ingest_audio(
        audio,
        "ar",
        "tent_a",
        whisper=_WhisperStub(
            "أنا مريم أبحث عن أخي يوسف وابني محمد عمره 8 سنوات "
            "فقدنا قبل ثلاثة أيام عند البوابة الجنوبية"
        ),
        ollama=ollama,
        storage=storage,
    )

    assert record.full_name_source_script == "يوسف"
    assert record.searcher_name == "مريم"
    assert record.last_seen_location == "البوابة الجنوبية"

    # Both missing persons must be in the roster.
    assert len(record.family_roster) == 2
    roster_names = {m.name for m in record.family_roster}
    assert "يوسف" in roster_names
    assert "محمد" in roster_names

    mohamad = next(m for m in record.family_roster if m.name == "محمد")
    assert mohamad.age == 8
    assert mohamad.status == "missing"


# ─── 11. Single-entity Carlos: family_roster has exactly 1 entry ────


@pytest.mark.asyncio
async def test_single_missing_person_carlos_roster_has_one_entry(
    tmp_path: Path,
) -> None:
    """Single-entity case: _ensure_primary_in_roster appends Carlos as
    the sole roster entry. No regression from the existing Carlos happy-path.
    """
    storage = _adapter(tmp_path)
    audio = _audio(tmp_path)

    ollama = _OllamaStub(
        english="I am looking for my son Carlos.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )

    record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=_WhisperStub("Estoy buscando a mi hijo Carlos."),
        ollama=ollama,
        storage=storage,
    )

    assert record.full_name_source_script == "Carlos"
    assert len(record.family_roster) == 1
    assert record.family_roster[0].name == "Carlos"
    assert record.family_roster[0].relationship_to_searcher == "hijo"
    assert record.family_roster[0].status == "missing"


# ─── 12. _detect_present_status tags co-located member as present ───


def test_detect_present_status_tags_aisha_present() -> None:
    """Yusuf demo case: 'زوجتي عائشة معي' → Aisha status='present'."""
    args = ExtractIntakeFieldsArgs(
        full_name="مريم",
        relationship="أخت",
        family_members=[
            FamilyMemberArg(name="مريم", relationship_to_searcher="أخت", status="missing"),
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن أخت", status="missing"),
            FamilyMemberArg(name="عائشة", relationship_to_searcher="زوجة", status="missing"),
        ],
    )
    transcription = "أبحث عن أختي مريم وابن أختي محمد، زوجتي عائشة معي"

    result = _detect_present_status(args, transcription)

    assert result.family_members is not None
    by_name = {m.name: m for m in result.family_members}
    assert by_name["عائشة"].status == "present"
    assert by_name["مريم"].status == "missing"
    assert by_name["محمد"].status == "missing"


# ─── 13. _detect_present_status leaves status unchanged when no marker ─


def test_detect_present_status_no_marker_leaves_missing() -> None:
    """No presence marker near the name → status stays 'missing'."""
    args = ExtractIntakeFieldsArgs(
        full_name="عائشة",
        relationship="زوجة",
        family_members=[
            FamilyMemberArg(name="عائشة", relationship_to_searcher="زوجة", status="missing"),
        ],
    )
    transcription = "أبحث عن عائشة"  # no presence marker

    result = _detect_present_status(args, transcription)

    assert result.family_members is not None
    assert result.family_members[0].status == "missing"


# ─── 14. _ensure_primary_in_roster guards against searcher conflation ─


def test_ensure_primary_in_roster_skips_when_full_name_equals_searcher_name() -> None:
    """Gemma sometimes conflates speaker with primary missing person on
    crisis audio (e.g. transcript ends with 'I cannot go on, I am Yusuf').
    Observed on Yusuf Take 4: full_name = searcher_name = 'يوسف العمار'.
    Without this guard, _ensure_primary_in_roster would copy the searcher
    into family_members, growing the roster to 4 entries and triggering
    the _fill_transliterations cascade-shift.
    """
    args = ExtractIntakeFieldsArgs(
        searcher_name="يوسف العمار",
        full_name="يوسف العمار",  # Gemma wrongly set primary = searcher
        family_members=[
            FamilyMemberArg(name="مريم", relationship_to_searcher="أخت", status="missing"),
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن أختي", status="missing"),
            FamilyMemberArg(name="عائشة", relationship_to_searcher="زوجة", status="present"),
        ],
    )

    result = _ensure_primary_in_roster(args)

    # Roster must NOT grow — Yusuf the searcher is not a missing person.
    assert result.family_members is not None
    assert len(result.family_members) == 3
    names = [m.name for m in result.family_members]
    assert "يوسف العمار" not in names
    assert names == ["مريم", "محمد", "عائشة"]


# ─── 15. _extract_member_ages handles Arabic word-numbers ──────────


def test_extract_member_ages_word_numbers_yusuf_take4() -> None:
    """Take 4 transcript states ages as Arabic words: 'مريم عمرها اثنان
    وثلاثون سنة' (Mariam is 32) and 'محمد عمره ثمان سنوات' (Mohammed is 8).
    The original digit-only regex missed these. Word-number preprocessing
    catches them and proximity-assigns to the right members.
    """
    transcription = (
        "أنا يوسف العمار عمري واحد واربعون سنة "
        "أبحث عن أختي مريم عمرها اثنان وثلاثون سنة "
        "وابن أختي محمد عمره ثمان سنوات "
        "زوجتي عائشة معي"
    )
    args = ExtractIntakeFieldsArgs(
        searcher_name="يوسف العمار",
        age=41,
        full_name="مريم",
        family_members=[
            FamilyMemberArg(name="مريم", relationship_to_searcher="أخت", status="missing"),
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن أختي", status="missing"),
            FamilyMemberArg(name="عائشة", relationship_to_searcher="زوجة", status="present"),
        ],
    )

    result = _extract_member_ages(args, transcription)

    assert result.family_members is not None
    by_name = {m.name: m for m in result.family_members}
    assert by_name["مريم"].age == 32
    assert by_name["محمد"].age == 8
    # Searcher's word-age "واحد واربعون" must NOT leak onto a family member.
    # Aisha is closest to that age phrase but should stay age=None.
    assert by_name["عائشة"].age is None


def test_extract_member_ages_word_numbers_searcher_age_excluded() -> None:
    """Searcher's first-person age statement must not be proximity-matched
    to a family member, regardless of word vs. digit form.
    """
    transcription = "أنا أحمد عمري ثلاثة وثلاثون سنة أبحث عن ابني يوسف"
    args = ExtractIntakeFieldsArgs(
        searcher_name="أحمد",
        age=33,
        full_name="يوسف",
        family_members=[
            FamilyMemberArg(name="يوسف", relationship_to_searcher="ابن", status="missing"),
        ],
    )

    result = _extract_member_ages(args, transcription)
    assert result.family_members is not None
    # Yusuf has no stated age — searcher's 33 must not leak onto him.
    assert result.family_members[0].age is None


# ─── 16. _fill_transliterations anti-cascade (searcher-first) ────


def test_fill_transliterations_no_cascade_when_searcher_preset() -> None:
    """When _fill_searcher_name runs first and sets
    searcher_name_transliteration, _fill_transliterations must skip the
    searcher AND mark the searcher's English token as 'used' so family
    members don't compete for it. Without that bookkeeping, the
    second-closest English token would be wrongly absorbed by the first
    family member, cascading through the rest.
    """
    transcription = (
        "أنا يوسف العمار عمري واحد واربعون سنة "
        "أبحث عن أختي مريم وابن أختي محمد"
    )
    english = (
        "I am Youssef Al Ammar I am forty-one years old "
        "I am looking for my sister Mariam and my nephew Mohammed"
    )
    args = ExtractIntakeFieldsArgs(
        searcher_name="يوسف العمار",
        searcher_name_transliteration="Youssef Al Ammar",  # already set
        full_name="مريم",
        family_members=[
            FamilyMemberArg(name="مريم", relationship_to_searcher="أخت", status="missing"),
            FamilyMemberArg(name="محمد", relationship_to_searcher="ابن أختي", status="missing"),
        ],
    )

    result = _fill_transliterations(args, transcription, english)

    assert result.family_members is not None
    by_name = {m.name: m for m in result.family_members}
    # Mariam must get "Mariam" — NOT shifted to "Mohammed"
    assert by_name["مريم"].name_transliteration == "Mariam"
    # Mohammed must get "Mohammed" — NOT shifted to something else
    assert by_name["محمد"].name_transliteration == "Mohammed"
