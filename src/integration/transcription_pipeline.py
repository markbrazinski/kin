"""Two-stage orchestrator: Whisper ASR → Gemma translation → TranscriptionResult.

Lives in Integration because both stages are I/O. The pipeline is
stateless; adapters are constructor-injected so probes and the demo
share the same configuration without re-instantiating the underlying
WhisperModel (47s load) or Ollama client per call.

English short-circuits the Gemma translate call: Whisper already
produced English text, and routing it through Gemma adds latency and a
non-zero risk of fabricated commentary for no quality gain.

S4 adds `ingest_audio()` — the end-to-end entry point that runs
transcription + translation, classifies for crisis content, runs Gemma
tool-calling extraction (on the SOURCE-language text, matching Apr 28
hello-world + Apr 29 multilang sweep probe conditions), and persists
the result as an IntakeRecord with auto-emitted audit events. Crisis
inputs skip extraction entirely and route to a paused_for_crisis
record with a hardcoded referral.

ingest_audio emits all field_extracted events at once after a single
tool_call (one bulk update). Beat 5 turn-by-turn appearance is the
SSE brief's concern via sequential audio files or staggered rendering.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import structlog

from core import safety_rules
from core.matching import match_records
from core.rfl_schema import (
    Age,
    Guardian,
    LastSeen,
    Name,
    RFLRecord,
    TranscriptionResult,
)
from core.storage_schemas import IntakeRecord, MatchLink
from core.tool_calling import ToolCallResult
from integration.extraction_tools import (
    EXTRACT_INTAKE_FIELDS_TOOL,
    ExtractIntakeFieldsArgs,
)
from integration.storage_adapter import StorageAdapter

log = structlog.get_logger(__name__)


class _Transcriber(Protocol):
    async def transcribe(self, audio_path: Path, lang: str) -> str: ...


class _Translator(Protocol):
    async def translate(self, text: str, source_lang: str) -> str: ...


class _OllamaPort(Protocol):
    """Combined translate + tool_call duck-typed port for ingest_audio.

    OllamaAdapter satisfies both halves; tests pass a stub that
    implements both methods. Kept distinct from `_Translator` so
    `transcribe_and_translate` (which only needs translate) is
    not retrofitted with extraction concerns.
    """

    async def translate(self, text: str, source_lang: str) -> str: ...

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult: ...


_LATIN_SCRIPT_LANGS: frozenset[str] = frozenset({"en", "es", "fr"})

_LANG_TO_SOURCE_SCRIPT: dict[str, str] = {
    "en": "latin",
    "es": "latin",
    "fr": "latin",
    "ar": "arabic",
    "fa": "persian",
    "uk": "cyrillic",
}
"""Maps SupportedLanguage codes to RFLRecord.Name.source_script Literals.
Used by _to_rfl_record to bridge IntakeRecord (stores language code) to
RFLRecord (stores script name). Unknown langs default to 'other'."""

_REFERRAL_ORG_BY_LANG: dict[str, str] = {
    "en": "ICRC Family Links Network",
    "es": "ICRC Family Links Network",
    "ar": "ICRC Family Links Network",
    "fa": "IFRC Family Links Network",
    "fr": "ICRC Family Links Network",
    "uk": "UNHCR Family Links",
}
"""TODO(caseworker review): the FA→IFRC and UK→UNHCR splits are the
plan's working assumption, not specced. Review with regional ICRC /
IFRC / UNHCR field offices before demo lock-in."""

_EXTRACTION_SYSTEM_PROMPT = (
    "You are an intake assistant. When the user describes a missing "
    "person, call extract_intake_fields with the fields the user "
    "stated. Do not invent fields the user did not state — pass null "
    "for unknown values."
)


@dataclass
class PipelineMetrics:
    whisper_latency_s: float
    gemma_latency_s: float
    total_latency_s: float
    skipped_translation: bool


async def transcribe_and_translate(
    audio_path: Path,
    lang: str,
    *,
    whisper: _Transcriber,
    ollama: _Translator,
) -> TranscriptionResult:
    """Demo-facing convenience wrapper. Drops the metrics tuple."""
    result, _metrics = await transcribe_and_translate_with_metrics(
        audio_path, lang, whisper=whisper, ollama=ollama
    )
    return result


async def transcribe_and_translate_with_metrics(
    audio_path: Path,
    lang: str,
    *,
    whisper: _Transcriber,
    ollama: _Translator,
) -> tuple[TranscriptionResult, PipelineMetrics]:
    """Run Whisper then Gemma; assemble TranscriptionResult; report stage timings.

    Adapter exceptions propagate unchanged. The pipeline does not
    convert PaddingFailed, InferenceTimeout, etc. — callers handle the
    shared adapter error vocabulary directly.
    """
    log.info("pipeline_start", audio_path=str(audio_path), lang=lang)

    t0 = time.perf_counter()
    source_text = await whisper.transcribe(audio_path, lang)
    t1 = time.perf_counter()
    whisper_latency_s = t1 - t0

    if lang == "en":
        english = source_text
        gemma_latency_s = 0.0
        skipped = True
    else:
        english = await ollama.translate(source_text, lang)
        gemma_latency_s = time.perf_counter() - t1
        skipped = False

    total_latency_s = time.perf_counter() - t0
    metrics = PipelineMetrics(
        whisper_latency_s=whisper_latency_s,
        gemma_latency_s=gemma_latency_s,
        total_latency_s=total_latency_s,
        skipped_translation=skipped,
    )

    log.info(
        "pipeline_complete",
        audio_path=str(audio_path),
        lang=lang,
        whisper_latency_s=whisper_latency_s,
        gemma_latency_s=gemma_latency_s,
        total_latency_s=total_latency_s,
        skipped_translation=skipped,
    )

    result = TranscriptionResult(
        transcription=source_text, english_translation=english
    )
    return result, metrics


# ─── ingest_audio orchestration (S4) ─────────────────────────────


async def ingest_audio(
    audio_path: Path,
    lang: str,
    source_device_id: str,
    *,
    whisper: _Transcriber,
    ollama: _OllamaPort,
    storage: StorageAdapter,
) -> IntakeRecord:
    """End-to-end ingest: audio → IntakeRecord with audit trail.

    Runs Whisper transcription + Gemma translation (via
    transcribe_and_translate), classifies the SOURCE-language text for
    crisis keywords, and either:
      - on crisis: persists a paused_for_crisis record with referral
        info, skips extraction + matching trigger, returns.
      - on non-crisis: runs Gemma tool-calling extraction on the
        source-language text (matches Apr 28/29 probe conditions),
        persists a partial record, then updates with extracted fields
        (one field_extracted audit event per non-empty field).

    Failure mode: any upstream exception (Whisper PaddingFailed,
    Ollama InferenceTimeout, etc.) propagates unchanged. No
    defensive IntakeRecord is created on partial failure. Failed-
    intake recovery is a separate brief.

    Audit-event emission per Part 1 REV 4 / Part 2 REV 3 mapping. All
    field_extracted events fire at once after a single tool_call (one
    bulk update). Beat 5 turn-by-turn field appearance is achieved
    downstream (SSE brief): either three sequential audio files or
    staggered rendering. NOT an orchestration concern.

    S5 will wire matching trigger between the post-update step and
    the optional final status="complete" update.
    """
    log.info(
        "ingest_audio_start",
        audio_path=str(audio_path),
        lang=lang,
        source_device_id=source_device_id,
    )

    # Stage 1: Whisper + (optional) Gemma translate.
    # Exceptions propagate unchanged (Q2 locked).
    result = await transcribe_and_translate(
        audio_path, lang, whisper=whisper, ollama=ollama
    )

    # Stage 2: crisis classification on SOURCE text (Q5 locked).
    # safety_rules' keyword lists are language-keyed; English keywords
    # won't match Arabic/Persian crisis utterances.
    safety = safety_rules.classify(result.transcription, lang=lang)

    if safety.is_crisis:
        log.warning(
            "crisis_path_taken",
            lang=lang,
            source_device_id=source_device_id,
            matched_keyword_count=len(safety.matched_keywords),
        )
        return _persist_crisis_record(
            lang=lang,
            source_device_id=source_device_id,
            safety=safety,
            storage=storage,
        )

    # Stage 3: Gemma tool-calling extraction on SOURCE text (Q1 locked).
    # Exceptions propagate (InvalidToolCall, InferenceTimeout,
    # InferenceFailed, Pydantic ValidationError on args).
    messages = _build_extraction_messages(result.transcription)
    tool_result = await ollama.tool_call(
        messages=messages, tools=[EXTRACT_INTAKE_FIELDS_TOOL]
    )
    args = ExtractIntakeFieldsArgs(**tool_result.arguments)

    # Stage 4: map extraction → IntakeRecord fields (discrepancy #3).
    intake_fields = _map_extraction_to_intake(args, lang)

    # Stage 5: two-step persist for per-field audit events.
    record = storage.create_intake_record(
        language=lang,
        source_device_id=source_device_id,
        status="partial",
    )
    record = storage.update_intake_record(record.id, **intake_fields)

    # Stage 6: structlog minor_flagged signal (discrepancy #1).
    if intake_fields.get("is_minor"):
        log.info(
            "minor_flagged",
            record_id=str(record.id),
            age=intake_fields.get("age"),
            lang=lang,
        )

    # Stage 7: matching trigger. Pairwise fan-out vs every eligible
    # candidate; persists matches as proposed MatchLinks.
    await _trigger_matching(record, storage=storage)

    # Stage 8: promote to complete if invariants satisfied.
    if record.full_name_source_script and record.relationship_to_seeker:
        record = storage.update_intake_record(record.id, status="complete")

    log.info(
        "ingest_audio_complete",
        record_id=str(record.id),
        status=record.status,
        is_crisis=record.is_crisis,
        is_minor=record.is_minor,
        lang=lang,
    )
    return record


def _persist_crisis_record(
    *,
    lang: str,
    source_device_id: str,
    safety: safety_rules.SafetyResult,
    storage: StorageAdapter,
) -> IntakeRecord:
    """Crisis-path persistence: create partial then update to
    paused_for_crisis to trigger the spec-mandated triple-emit
    (intake_paused → crisis_detected → referral_issued) plus
    field_extracted events for the crisis fields.
    """
    referral_org = _REFERRAL_ORG_BY_LANG.get(lang, "ICRC Family Links Network")
    crisis_match_path = "keyword" if safety.matched_keywords else None

    record = storage.create_intake_record(
        language=lang,
        source_device_id=source_device_id,
        status="partial",
    )
    record = storage.update_intake_record(
        record.id,
        status="paused_for_crisis",
        is_crisis=True,
        crisis_match_path=crisis_match_path,
        referral_issued=True,
        referral_organization=referral_org,
    )
    return record


def _build_extraction_messages(text: str) -> list[dict[str, Any]]:
    """Same shape as Apr 28 hello-world + Apr 29 multilang sweep.

    System prompt frames the tool-calling expectation; user message is
    the source-language text directly (Q1 locked: source text matches
    probe conditions and preserves source-language fields downstream).
    """
    return [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]


def _map_extraction_to_intake(
    args: ExtractIntakeFieldsArgs,
    lang: str,
) -> dict[str, Any]:
    """Map extracted args → IntakeRecord field overrides per discrepancy #3.

    Latin-script langs (en/es/fr): full_name populates BOTH
    full_name_source_script and full_name_transliteration (the
    transliteration is just the same Latin string).

    Non-Latin langs (ar/fa/uk): full_name populates only
    full_name_source_script; full_name_transliteration stays empty for
    the worker to enter later (Part 1 REV 4 working hypothesis).

    is_minor is derived from age: True iff age is set and < 18.
    """
    full_name = args.full_name
    is_latin = lang in _LATIN_SCRIPT_LANGS
    is_minor = args.age is not None and args.age < 18

    return {
        "full_name_source_script": full_name,
        "full_name_transliteration": full_name if is_latin else "",
        "relationship_to_seeker": args.relationship,
        "age": args.age,
        "is_minor": is_minor,
    }


# ─── Matching trigger (S5) ───────────────────────────────────────


def _source_script_for_lang(lang: str) -> str:
    """Map IntakeRecord language code to RFLRecord.Name.source_script.

    Unknown langs default to 'other' (legal Literal value on Name).
    """
    return _LANG_TO_SOURCE_SCRIPT.get(lang, "other")


def _to_rfl_record(intake: IntakeRecord) -> RFLRecord:
    """Map a flat IntakeRecord to a nested RFLRecord for matching.

    Storage owns the persistence shape (flat); matching owns the
    domain shape (nested). This helper bridges them without
    refactoring either. Missing intake fields become None on the RFL
    side so matching's gate + corroborating logic sees clean signals
    (matching gracefully no-ops on absent sub-models).

    distinguishing_marks: IntakeRecord stores a single str | None;
    RFLRecord expects list[str]. Wrap non-empty single string in a
    one-element list (S5 plan Q2).
    """
    if intake.full_name_source_script:
        transliterations = (
            [intake.full_name_transliteration]
            if intake.full_name_transliteration
            else []
        )
        name: Name | None = Name(
            canonical=intake.full_name_source_script,
            source_script=_source_script_for_lang(intake.language),  # type: ignore[arg-type]
            transliterations=transliterations,
        )
    else:
        name = None

    if intake.age is not None:
        age: Age | None = Age(value=intake.age, confidence="exact")
    else:
        age = None

    last_seen: LastSeen | None = None
    if intake.last_seen_location or intake.last_seen_date:
        last_seen = LastSeen(
            location=intake.last_seen_location,
            date_text=intake.last_seen_date,
        )

    marks = (
        [intake.distinguishing_marks]
        if intake.distinguishing_marks
        else []
    )

    return RFLRecord(
        name=name,
        age=age,
        relationship=intake.relationship_to_seeker or None,
        last_seen=last_seen,
        guardian=Guardian(present=False, consent=False),
        distinguishing_marks=marks,
    )


async def _trigger_matching(
    new_record: IntakeRecord,
    *,
    storage: StorageAdapter,
) -> list[MatchLink]:
    """Fan-out matching: pairwise match_records vs every eligible
    candidate; persist hits as proposed MatchLinks.

    Filters per Part 1 REV 4 §"Required matching trigger behavior":
      - drop self (don't self-match)
      - drop candidates with status=paused_for_crisis (excluded from
        candidate pool)
      - partial records DO enter the pool

    The matching algorithm (core.matching.match_records) is unchanged;
    this wrapper is the orchestration-layer entry point. Each match
    becomes a MatchLink in verification_status='proposed' via
    storage.create_match_link, which auto-emits one match_proposed
    audit event per link.

    Emits structlog matching_trigger_fired regardless of match count
    so trigger execution is observable in the audit stream even when
    no matches result. Returns the list of created MatchLinks.

    See ADR-004 for the placement rationale (orchestration, not
    storage). See docs/matching.md §9 for the trigger contract.
    """
    all_records = storage.list_intake_records()
    candidates = [
        r
        for r in all_records
        if r.id != new_record.id and r.status != "paused_for_crisis"
    ]

    new_rfl = _to_rfl_record(new_record)
    created_links: list[MatchLink] = []

    for candidate in candidates:
        result = match_records(new_rfl, _to_rfl_record(candidate))
        if not result.is_match:
            continue
        match_reasoning = {
            "matched_fields": list(result.matched_fields),
            "phonetic_score": result.phonetic_score,
            "reason": result.reason,
        }
        link = storage.create_match_link(
            record_a_id=new_record.id,
            record_b_id=candidate.id,
            confidence_band=result.confidence,
            confidence_score=result.score,
            match_reasoning=match_reasoning,
        )
        created_links.append(link)

    log.info(
        "matching_trigger_fired",
        new_record_id=str(new_record.id),
        candidate_count=len(candidates),
        match_count=len(created_links),
    )
    return created_links
