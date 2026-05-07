"""End-to-end tests for ingest_audio orchestration (S4).

Six tests cover happy path (Spanish Carlos), crisis path (Arabic
keyword utterance), partial-status when extraction omits relationship,
is_minor + minor_flagged structlog signal, native-script preservation
(Arabic), and Whisper-failure propagation.

Stubs follow test_transcription_pipeline.py patterns. Real
StorageAdapter with tmp_path + FakeClock; matching trigger is S5
(deferred match-fires test).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import structlog

from core.tool_calling import ToolCallResult
from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import ingest_audio
from integration.whisper_adapter import PaddingFailed
from tests.fakes.fake_clock import FakeClock

# ─── Stubs (mirror test_transcription_pipeline.py patterns) ───────


class _WhisperStub:
    def __init__(self, text: str = "hola") -> None:
        self._text = text
        self.calls: list[tuple[Path, str]] = []

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        self.calls.append((audio_path, lang))
        return self._text


class _OllamaStub:
    """Combined translate + tool_call duck-typed port.

    translate_calls and tool_call_calls let tests assert which path
    fired. tool_call_response is configured per-test; if None and
    tool_call() is invoked, the stub raises a clear error so an
    accidentally-fired tool_call fails the test loud.
    """

    def __init__(
        self,
        english: str = "hello",
        tool_call_response: ToolCallResult | None = None,
    ) -> None:
        self._english = english
        self._tool_call_response = tool_call_response
        self.translate_calls: list[tuple[str, str]] = []
        self.tool_call_calls: list[
            tuple[list[dict[str, Any]], list[dict[str, Any]]]
        ] = []

    async def translate(self, text: str, source_lang: str) -> str:
        self.translate_calls.append((text, source_lang))
        return self._english

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult:
        self.tool_call_calls.append((messages, tools))
        if self._tool_call_response is None:
            raise AssertionError(
                "_OllamaStub.tool_call invoked without configured response"
            )
        return self._tool_call_response


class _RaisingWhisper:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.call_count = 0

    async def transcribe(self, audio_path: Path, lang: str) -> str:
        self.call_count += 1
        raise self._error


def _adapter(tmp_path: Path) -> StorageAdapter:
    return StorageAdapter(tmp_path / "storage", FakeClock())


def _audio_path(tmp_path: Path) -> Path:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"")
    return audio


# ─── 1. Happy path Spanish Carlos ─────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_happy_path_spanish_carlos(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(text="Estoy buscando a mi hijo Carlos.")
    ollama = _OllamaStub(
        english="I am looking for my son Carlos.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )

    record, locale_message = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    # ADR-004 REV 3: non-crisis branch returns (record, None).
    assert locale_message is None

    # Returned record fields.
    assert record.full_name_source_script == "Carlos"
    assert record.full_name_transliteration == "Carlos"  # Latin lang
    assert record.relationship_to_seeker == "hijo"
    assert record.age is None
    assert record.is_minor is False
    assert record.is_crisis is False
    assert record.status == "complete"  # both required fields populated
    assert record.language == "es"
    assert record.source_device_id == "tent_a"

    # tool_call invoked once with SOURCE text (Q1 lock).
    assert len(ollama.tool_call_calls) == 1
    tool_messages, tool_tools = ollama.tool_call_calls[0]
    user_msg = next(m for m in tool_messages if m["role"] == "user")
    assert user_msg["content"] == "Estoy buscando a mi hijo Carlos."

    # Audit events: intake_created → field_extracted (≥3).
    events = storage.list_audit_events()
    assert events[0].event_type == "intake_created"
    field_extracted_events = [
        e for e in events if e.event_type == "field_extracted"
    ]
    assert len(field_extracted_events) >= 3
    field_names = {e.details["field_name"] for e in field_extracted_events}
    assert "full_name_source_script" in field_names
    assert "relationship_to_seeker" in field_names
    assert "full_name_transliteration" in field_names


# ─── 2. Crisis path Arabic ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_crisis_path_arabic_skips_extraction(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    # "اقتلني" is a real keyword from _CRISIS_KEYWORDS["ar"].
    whisper = _WhisperStub(text="اقتلني الآن")
    # S6: crisis branch invokes Gemma escalate_crisis (locale-aware
    # formatter; safety_rules.classify is the gate). Configure the
    # stub to return a valid escalate_crisis result so extract_intake_fields
    # is the only thing that must be skipped.
    ollama = _OllamaStub(
        english="kill me now",
        tool_call_response=ToolCallResult(
            name="escalate_crisis",
            arguments={
                "referral_organization": "الصليب الأحمر",
                "locale_aware_message": "يرجى الاتصال بالرقم...",
            },
        ),
    )

    record, locale_message = await ingest_audio(
        audio,
        "ar",
        "tent_b",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    assert record.status == "partial"
    assert record.is_crisis is True
    assert record.crisis_match_path == "keyword"
    assert record.referral_issued is True
    # S6: Gemma override populates referral_organization (locale-aware).
    assert record.referral_organization == "الصليب الأحمر"
    # ADR-004 REV 3: crisis branch surfaces locale_aware_message
    # through the tuple return for the route layer.
    assert locale_message == "يرجى الاتصال بالرقم..."

    # extract_intake_fields skipped; escalate_crisis invoked once.
    assert len(ollama.tool_call_calls) == 1
    _msgs, tools = ollama.tool_call_calls[0]
    tool_names = {t["function"]["name"] for t in tools}
    assert tool_names == {"escalate_crisis"}

    # Audit events ordered: created → crisis dual-emit → field_extracted ×N.
    event_types = [e.event_type for e in storage.list_audit_events()]
    assert event_types[0] == "intake_created"
    assert event_types[1] == "crisis_detected"
    assert event_types[2] == "referral_issued"
    # Remainder are field_extracted for is_crisis, crisis_match_path,
    # referral_issued, referral_organization.
    assert all(et == "field_extracted" for et in event_types[3:])
    assert len(event_types[3:]) == 4


# ─── 3. Partial status when relationship missing ──────────────────


@pytest.mark.asyncio
async def test_ingest_audio_partial_status_when_relationship_missing(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(text="Maria")
    ollama = _OllamaStub(
        english="Maria",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Maria", "relationship": ""},
        ),
    )

    record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    assert record.full_name_source_script == "Maria"
    assert record.relationship_to_seeker == ""
    assert record.status == "partial"  # complete rule not satisfied


# ─── 4. is_minor + minor_flagged structlog signal ─────────────────


@pytest.mark.asyncio
async def test_ingest_audio_minor_age_emits_minor_flagged_structlog(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(text="Estoy buscando a mi hijo Carlos. Tiene 8 años.")
    ollama = _OllamaStub(
        english="I am looking for my son Carlos. He is 8 years old.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "Carlos",
                "relationship": "hijo",
                "age": 8,
            },
        ),
    )

    with structlog.testing.capture_logs() as cap_logs:
        record, _ = await ingest_audio(
            audio,
            "es",
            "tent_a",
            whisper=whisper,
            ollama=ollama,
            storage=storage,
        )

    assert record.age == 8
    assert record.is_minor is True

    events = [log["event"] for log in cap_logs]
    assert "minor_flagged" in events


# ─── 5. Arabic native-script preservation ─────────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_arabic_native_script_preservation(
    tmp_path: Path,
) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(
        text="أبحث عن ابني محمد. عمره ثماني سنوات."
    )
    ollama = _OllamaStub(
        english="I am looking for my son Mohammed. He is eight years old.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "محمد",
                "relationship": "ابن",
                "age": 8,
            },
        ),
    )

    record, _ = await ingest_audio(
        audio,
        "ar",
        "tent_a",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    # Source-script preserved verbatim; transliteration left empty
    # (worker-entered, per discrepancy #3).
    assert record.full_name_source_script == "محمد"
    assert record.full_name_transliteration == ""
    assert record.relationship_to_seeker == "ابن"
    assert record.age == 8
    assert record.is_minor is True


# ─── 6. Whisper failure propagates ────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_propagates_whisper_failure(tmp_path: Path) -> None:
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _RaisingWhisper(PaddingFailed("ffmpeg padding failed"))
    ollama = _OllamaStub()

    with pytest.raises(PaddingFailed):
        await ingest_audio(
            audio,
            "es",
            "tent_a",
            whisper=whisper,
            ollama=ollama,
            storage=storage,
        )

    # No record persisted, no audit events.
    assert storage.list_intake_records() == []
    assert storage.list_audit_events() == []


# ─── 7. Match fires on second Mohamad ingest (deferred from S4) ───


@pytest.mark.asyncio
async def test_ingest_audio_match_fires_on_second_mohamad_ingest(
    tmp_path: Path,
) -> None:
    """Two Arabic Mohamad intakes from separate devices should produce
    one MatchLink + one match_proposed audit event after the second
    ingest. Exercises the S5 matching trigger end-to-end through
    ingest_audio.

    Uses two _OllamaStub instances (one per ingest call) since the
    stub's tool_call_response is a single value per instance — simpler
    than queueing responses on a single stub.
    """
    storage = _adapter(tmp_path)
    audio_a = tmp_path / "tent_a.wav"
    audio_a.write_bytes(b"")
    audio_b = tmp_path / "tent_b.wav"
    audio_b.write_bytes(b"")

    arabic_input = "أبحث عن ابني محمد. عمره ثماني سنوات."

    whisper_a = _WhisperStub(text=arabic_input)
    ollama_a = _OllamaStub(
        english="I am looking for my son Mohammed. He is eight years old.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "محمد",
                "relationship": "ابن",
                "age": 8,
            },
        ),
    )
    record_a, _ = await ingest_audio(
        audio_a,
        "ar",
        "tent_a",
        whisper=whisper_a,
        ollama=ollama_a,
        storage=storage,
    )
    assert record_a.full_name_source_script == "محمد"
    assert storage.list_match_links() == []  # no candidates yet

    whisper_b = _WhisperStub(text=arabic_input)
    ollama_b = _OllamaStub(
        english="I am looking for my son Mohammed. He is eight years old.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={
                "full_name": "محمد",
                "relationship": "ابن",
                "age": 8,
            },
        ),
    )

    with structlog.testing.capture_logs() as cap_logs:
        record_b, _ = await ingest_audio(
            audio_b,
            "ar",
            "tent_b",
            whisper=whisper_b,
            ollama=ollama_b,
            storage=storage,
        )

    # Exactly one MatchLink, proposed status, between record_a and
    # record_b.
    links = storage.list_match_links()
    assert len(links) == 1
    link = links[0]
    assert link.record_a_id == record_b.id
    assert link.record_b_id == record_a.id
    assert link.verification_status == "proposed"
    assert link.confidence_band == "high"  # same-script-exact + age + relationship
    assert link.proposed_by == "kin_matching_v1"

    # Bundle 1.5 S5: matching trigger now ALWAYS emits match_proposed.
    # First ingest (record_a) triggered an empty-result run that
    # emitted a summary event with record_ids=[record_a.id] and
    # candidate_count=0; this second ingest's per-match emission
    # adds a second event with both records and candidate_count=1.
    proposed_events = storage.list_audit_events(event_type="match_proposed")
    assert len(proposed_events) == 2
    # The first event is the empty summary from record_a's ingest.
    assert proposed_events[0].record_ids == [record_a.id]
    assert proposed_events[0].candidate_count == 0
    assert proposed_events[0].match_id is None
    # The second event is the per-match emission from this ingest.
    assert set(proposed_events[1].record_ids) == {record_a.id, record_b.id}
    assert proposed_events[1].candidate_count == 1
    assert proposed_events[1].match_id == link.id

    # matching_trigger_fired emitted with match_count=1 on the second
    # ingest. (The first ingest also fired it with match_count=0, but
    # that's outside this capture_logs window.)
    trigger_events = [
        log for log in cap_logs if log["event"] == "matching_trigger_fired"
    ]
    assert len(trigger_events) == 1
    assert trigger_events[0]["match_count"] == 1
    assert trigger_events[0]["candidate_count"] == 1


# ─── S6 crisis-branch tests (5–7) ─────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_audio_crisis_path_uses_gemma_referral(
    tmp_path: Path,
) -> None:
    """S6 happy path: Gemma escalate_crisis returns a locale-aware NGO
    name; that name is what lands on IntakeRecord.referral_organization,
    NOT the static _REFERRAL_ORG_BY_LANG entry.
    """
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(text="me suicido ahora")
    ollama = _OllamaStub(
        english="I'm killing myself now",
        tool_call_response=ToolCallResult(
            name="escalate_crisis",
            arguments={
                "referral_organization": "Cruz Roja",
                "locale_aware_message": "Por favor llame a Cruz Roja al 911.",
            },
        ),
    )

    record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    # Gemma override populated; NOT the static lookup
    # ("ICRC Family Links Network" for es).
    assert record.referral_organization == "Cruz Roja"
    assert record.status == "partial"
    assert record.is_crisis is True
    assert record.crisis_match_path == "keyword"  # classifier still decided
    assert record.referral_issued is True

    # escalate_crisis invoked once; extract_intake_fields skipped.
    assert len(ollama.tool_call_calls) == 1
    _msgs, tools = ollama.tool_call_calls[0]
    assert {t["function"]["name"] for t in tools} == {"escalate_crisis"}


@pytest.mark.asyncio
async def test_ingest_audio_crisis_path_falls_back_to_static_lookup(
    tmp_path: Path,
) -> None:
    """S6 fallback: Gemma raises; safety path still completes with the
    static referral. Audit triple still emits in order.
    """
    from integration._errors import InferenceTimeout

    class _RaisingOllama(_OllamaStub):
        async def tool_call(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
        ) -> ToolCallResult:
            self.tool_call_calls.append((messages, tools))
            raise InferenceTimeout("simulated cold-start timeout")

    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    whisper = _WhisperStub(text="me suicido ahora")
    ollama = _RaisingOllama(english="I'm killing myself now")

    record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=whisper,
        ollama=ollama,
        storage=storage,
    )

    # Static fallback for es is "ICRC Family Links Network".
    assert record.referral_organization == "ICRC Family Links Network"
    assert record.status == "partial"
    assert record.is_crisis is True
    assert record.referral_issued is True

    # Audit dual-emit in order.
    event_types = [e.event_type for e in storage.list_audit_events()]
    assert event_types[0] == "intake_created"
    assert event_types[1] == "crisis_detected"
    assert event_types[2] == "referral_issued"


@pytest.mark.asyncio
async def test_ingest_audio_crisis_extend_still_raises_value_error(
    tmp_path: Path,
) -> None:
    """S5 lock #4 regression: extending an existing intake_id into a
    crisis turn raises ValueError BEFORE invoking Gemma. Locks the
    extend-incompatible invariant; ensures we don't burn a tool_call
    budget on misuse.
    """
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    # Seed a non-crisis record to extend INTO a crisis turn.
    seed_whisper = _WhisperStub(text="Estoy buscando a mi hijo Carlos.")
    seed_ollama = _OllamaStub(
        english="I am looking for my son Carlos.",
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "Carlos", "relationship": "hijo"},
        ),
    )
    seed_record, _ = await ingest_audio(
        audio,
        "es",
        "tent_a",
        whisper=seed_whisper,
        ollama=seed_ollama,
        storage=storage,
    )

    # Now extend with a crisis transcript. tool_call_response stays None
    # so any Gemma invocation (extract OR escalate) fails loud — proving
    # the ValueError fires before any Gemma path runs.
    crisis_whisper = _WhisperStub(text="me suicido ahora")
    crisis_ollama = _OllamaStub(english="kill myself", tool_call_response=None)

    with pytest.raises(ValueError, match="crisis path is create-only"):
        await ingest_audio(
            audio,
            "es",
            "tent_a",
            whisper=crisis_whisper,
            ollama=crisis_ollama,
            storage=storage,
            intake_id=seed_record.id,
        )

    # No Gemma tool_call invoked on the crisis-extend attempt.
    assert crisis_ollama.tool_call_calls == []


# ─── S15a: source_utterance + whisper_translation in field_extracted ─


@pytest.mark.asyncio
async def test_field_extracted_events_carry_source_utterance(
    tmp_path: Path,
) -> None:
    """S15a: field_extracted audit events emitted by ingest_audio must
    include source_utterance (Whisper source-language text) and
    whisper_translation (Whisper/Gemma English text) in their details.

    These fields power the audit panel's "Source Arabic / Whisper
    translation / Gemma extraction" sub-block labels.
    """
    storage = _adapter(tmp_path)
    audio = _audio_path(tmp_path)

    source_text = "أبحث عن ابني محمد. عمره ثماني سنوات."
    english_text = "I am looking for my son Mohammed. He is eight years old."

    whisper = _WhisperStub(text=source_text)
    ollama = _OllamaStub(
        english=english_text,
        tool_call_response=ToolCallResult(
            name="extract_intake_fields",
            arguments={"full_name": "محمد", "relationship": "ابن", "age": 8},
        ),
    )

    await ingest_audio(audio, "ar", "tent_a", whisper=whisper, ollama=ollama, storage=storage)

    field_extracted_events = storage.list_audit_events(event_type="field_extracted")
    assert len(field_extracted_events) >= 1

    for event in field_extracted_events:
        assert event.details.get("source_utterance") == source_text, (
            f"field_extracted event for {event.details.get('field_name')!r} "
            f"missing source_utterance"
        )
        assert event.details.get("whisper_translation") == english_text, (
            f"field_extracted event for {event.details.get('field_name')!r} "
            f"missing whisper_translation"
        )


@pytest.mark.asyncio
async def test_status_transition_events_omit_utterance_fields(
    tmp_path: Path,
) -> None:
    """Backward-compat: update_intake_record calls that don't pass
    source_utterance/whisper_translation (e.g. status promotions,
    crisis triple-emit) must not include those keys in event details.
    """
    storage = _adapter(tmp_path)
    record = storage.create_intake_record(language="ar", source_device_id="tent_a")
    # Status-only update — no utterance kwargs.
    storage.update_intake_record(record.id, status="complete")

    # Status-change field_extracted events must not carry utterance fields.
    for event in storage.list_audit_events():
        assert "source_utterance" not in event.details
        assert "whisper_translation" not in event.details
