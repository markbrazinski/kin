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
the result as an IntakeRecord with auto-emitted audit events.

ingest_audio emits all field_extracted events at once after a single
tool_call (one bulk update). Beat 5 turn-by-turn appearance is the
SSE brief's concern via sequential audio files or staggered rendering.

Crisis detection does NOT skip extraction. Extraction runs
unconditionally; crisis is classified first but the flag is applied
after extraction so the record is fully populated before the crisis
audit events (crisis_detected, referral_issued) fire.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import structlog
from pydantic import ValidationError

from core import safety_rules
from core.matching import (
    MatchResult,
    NetworkMatchResult,
    confidence_band_for_score,
    match_records,
    match_records_network,
)
from core.rfl_schema import (
    Age,
    FamilyMember,
    Guardian,
    LastSeen,
    Name,
    RFLRecord,
    TranscriptionResult,
)
from core.storage_schemas import IntakeRecord, MatchLink
from core.tool_calling import ToolCallResult
from integration._errors import AdapterError, InferenceFailed, InferenceTimeout, InvalidToolCall
from integration.escalate_crisis_tool import (
    ESCALATE_CRISIS_TOOL,
    EscalateCrisisArgs,
)
from integration.extraction_tools import (
    EXTRACT_INTAKE_FIELDS_TOOL,
    ExtractIntakeFieldsArgs,
    FamilyMemberArg,
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
    "\n\n"
    "If the speaker identifies themselves by name, populate "
    "searcher_name in the source script. If they state their "
    "relationship to the missing person, populate "
    "searcher_relationship_to_target."
    "\n\n"
    "Populate family_members with ALL missing persons the speaker "
    "names — this includes whoever is in full_name. If the speaker "
    "names a brother AND a son as missing, both appear in "
    "family_members (one entry each), and full_name holds the one "
    "they name first or emphasize most. Each entry requires name, "
    "relationship_to_searcher, and status. Set status='present' when "
    "the speaker says that person 'is with me' / 'معي' / 'is here "
    "with us' / 'is safe'. Otherwise set status='missing'. "
    "Emit null for family_members only when the speaker names no "
    "one at all."
    "\n\n"
    "Age assignment rule: the top-level 'age' field is ALWAYS the "
    "searcher's own age. When the searcher states a family member's "
    "age (e.g. 'my son Mohamad, he is 8 years old' / 'ابني محمد "
    "عمره 8 سنوات'), put that age on the family_members entry for "
    "that person, NOT on the top-level age field."
    "\n\n"
    "If the speaker describes HOW they became separated (e.g. crowd "
    "surge, bombing, fleeing in different directions, losing contact "
    "at a crossing), populate separation_circumstance in the source "
    "language. Null if no separation event is described."
    "\n\n"
    "CRITICAL RULES:\n"
    "1. The speaker (searcher) is NEVER a missing person. full_name "
    "and family_members must contain people OTHER than the searcher. "
    "If the transcript ends with the speaker restating their own "
    "name after a distress phrase (e.g. 'ما عد فيني انا يوسف' / "
    "'I cannot go on, I am Yusuf'), that is still the SEARCHER — "
    "do not put them in full_name or family_members.\n"
    "2. Each family member's age MUST go on that member's "
    "family_members entry whenever stated — in digits OR Arabic "
    "word-numbers. Arabic word-number map: واحد=1, اثنان=2, "
    "ثلاثة=3, اربعة=4, خمسة=5, ستة=6, سبعة=7, ثمان/ثمانية=8, "
    "تسعة=9, عشرة=10, اثنان وثلاثون=32, واحد واربعون=41.\n"
    "3. distinguishing_marks: when the speaker mentions a scar, "
    "mark, clothing, hair, or other identifying feature about a "
    "SPECIFIC family member, put that description on THAT MEMBER's "
    "family_members entry as their distinguishing_marks field. "
    "Do NOT put member-specific marks in the top-level "
    "distinguishing_features field — only use the top-level field "
    "for marks describing the primary missing person (full_name)."
    "\n\n"
    "WORKED EXAMPLE — study the input → output mapping:\n"
    "Input: \"أنا أحمد عمري 35 سنة أبحث عن ابنتي ليلى عمرها 12 سنة "
    "وأخي خالد عمره 28 سنة ليلى عندها ضفائر طويلة وخالد عنده ندبة على ذراعه\"\n"
    "(I am Ahmed, 35 years old, looking for my daughter Layla, 12, "
    "and my brother Khalid, 28; Layla has long braids and Khalid has "
    "a scar on his arm.)\n"
    "Correct extract_intake_fields call:\n"
    '{"searcher_name": "أحمد", "age": 35, "full_name": "ليلى", '
    '"relationship": "ابنة", "searcher_relationship_to_target": "أب", '
    '"family_members": ['
    '{"name": "ليلى", "relationship_to_searcher": "ابنة", '
    '"status": "missing", "age": 12, '
    '"distinguishing_marks": "ضفائر طويلة"}, '
    '{"name": "خالد", "relationship_to_searcher": "أخ", '
    '"status": "missing", "age": 28, '
    '"distinguishing_marks": "ندبة على ذراعه"}'
    ']}\n'
    "Notes: each member's age AND distinguishing_marks are attached "
    "to their own entry. The searcher (Ahmed) is NOT in "
    "family_members. The top-level distinguishing_features stays "
    "null because the marks belong to specific family members."
)

_CRISIS_SYSTEM_PROMPT = (
    "You are a humanitarian intake assistant. The system has already "
    "classified the user's message as a crisis using a deterministic "
    "keyword classifier. Do NOT re-evaluate whether this is a crisis — "
    "that decision has been made. Your only job is to call "
    "escalate_crisis with: (1) referral_organization — the name of an "
    "appropriate humanitarian referral organization in the speaker's "
    "language; (2) locale_aware_message — a brief calm message in the "
    "speaker's language directing them to immediate help. Do not assert "
    "facts about the person's situation. Do not promise outcomes. Two "
    "to three sentences for the message."
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
    intake_id: UUID | None = None,
) -> tuple[IntakeRecord, str | None]:
    """End-to-end ingest: audio → (IntakeRecord, locale_aware_message).

    intake_id=None (S4 default): create a new partial record with
    extracted fields. intake_id=X (S5 extend path): read record X,
    merge new turn's extracted fields, fire matching re-trigger if
    identity-bearing fields changed. The crisis path is create-only;
    extending into a crisis turn raises ValueError (guard fires after
    extraction, before crisis persistence).

    Returns a 2-tuple. The second element is `locale_aware_message`,
    Gemma's escalate_crisis short message in the speaker's language.
    It is non-None ONLY on the crisis branch and ONLY when the
    Gemma tool_call succeeded (fallback returns None). The route
    layer surfaces it on the synchronous POST response so the crisis
    overlay can open with body text atomic to the trigger; see
    ADR-004 REV 3. The message is ephemeral — not persisted to
    IntakeRecord, AuditEvent, or JSONL (REV 2 ephemerality lock).

    Failure mode: any upstream exception (Whisper PaddingFailed,
    Ollama InferenceTimeout, etc.) propagates unchanged. No
    defensive IntakeRecord is created on partial failure.

    Audit-event emission per Part 1 REV 4 / Part 2 REV 3 mapping.
    Each turn's update_intake_record emits one field_extracted event
    per changed field; storage's no-op detection skips unchanged
    fields, so a turn-2 audio that re-states the name doesn't
    re-fire field_extracted for it.
    """
    log.info(
        "ingest_audio_start",
        audio_path=str(audio_path),
        lang=lang,
        source_device_id=source_device_id,
        intake_id=str(intake_id) if intake_id else None,
    )

    # Stage 1: Whisper + (optional) Gemma translate.
    result = await transcribe_and_translate(
        audio_path, lang, whisper=whisper, ollama=ollama
    )

    # Emit transcription to SSE structlog stream so the transcript strip
    # in the React UI receives real utterance text (not mock data).
    log.info(
        "transcription_chunk",
        source=result.transcription,
        translation=result.english_translation,
        lang=lang,
        source_device_id=source_device_id,
    )

    # Stage 2: crisis classification on SOURCE text. Captured here but
    # NOT acted on yet — extraction runs unconditionally so the record
    # is fully populated before the crisis flag fires (see Stage 8).
    safety = safety_rules.classify(result.transcription, lang=lang)

    if safety.is_crisis:
        log.warning(
            "crisis_path_taken",
            lang=lang,
            source_device_id=source_device_id,
            matched_keyword_count=len(safety.matched_keywords),
        )

    # Stage 3: Gemma tool-calling extraction on SOURCE text.
    messages = _build_extraction_messages(result.transcription)
    tool_result = await ollama.tool_call(
        messages=messages, tools=[EXTRACT_INTAKE_FIELDS_TOOL]
    )
    args = ExtractIntakeFieldsArgs(**tool_result.arguments)

    # Stage 3b: English-translation fallback.
    # On crisis audio, Gemma sometimes returns all-null fields on the
    # source-language pass (distress content causes early stop). If
    # extraction yielded nothing extractable, retry on the English
    # translation so the RecordCard is not blank.
    if _extraction_is_empty(args) and result.english_translation != result.transcription:
        log.info(
            "extraction_empty_fallback_en",
            lang=lang,
            source_device_id=source_device_id,
        )
        en_messages = _build_extraction_messages(result.english_translation)
        en_tool_result = await ollama.tool_call(
            messages=en_messages, tools=[EXTRACT_INTAKE_FIELDS_TOOL]
        )
        args = ExtractIntakeFieldsArgs(**en_tool_result.arguments)

    args = _ensure_primary_in_roster(args)
    args = _detect_present_status(args, result.transcription)
    args = _extract_member_ages(args, result.transcription)
    args = _promote_first_missing_to_primary(args)
    # Gemma sometimes bundles location+date+verb into separation_circumstance
    # (e.g. 'فقدنا قبل ثلاثة أيام عند البوابة الجنوبية' on Mariam Take 2).
    # Backstop: when last_seen_location is null AND the circumstance string
    # contains an Arabic location preposition + place name, split them out.
    args = _split_location_from_circumstance(args)
    # Backfill searcher_name BEFORE _fill_transliterations runs — otherwise
    # the searcher's transliteration step inside _fill_transliterations
    # consumes a candidate from the English token pool and offsets all
    # subsequent family-member matches by one (cascade-shift bug observed
    # on Take 4). Setting searcher_name + its transliteration first lets
    # _fill_transliterations skip the searcher and align family members
    # to their own English tokens directly.
    if lang not in _LATIN_SCRIPT_LANGS and not args.searcher_name:
        args = _fill_searcher_name(args, result.transcription, result.english_translation)
    # For non-Latin languages, fill missing name_transliteration using
    # proximity matching against the Whisper English translation.
    if lang not in _LATIN_SCRIPT_LANGS:
        args = _fill_transliterations(args, result.transcription, result.english_translation)

    # For non-Latin languages, translate per-member distinguishing_marks
    # via a short Gemma translate call. Caseworker-side UI shows the
    # Arabic source + English translation side-by-side. One translate
    # call per member with marks (~0.3s warm) — typically 0–1 per intake.
    if lang not in _LATIN_SCRIPT_LANGS:
        args = await _translate_member_marks(args, lang, ollama=ollama)

    # Same pattern for last_seen_location at the record level: caseworkers
    # need an English form of "البوابة الجنوبية" → "Southern gate" to
    # render alongside the Arabic source. One translate call when present.
    if (
        lang not in _LATIN_SCRIPT_LANGS
        and args.last_seen_location
        and not args.last_seen_location_transliteration
    ):
        try:
            en = (await ollama.translate(args.last_seen_location, lang)).strip()
            if en:
                args = args.model_copy(
                    update={"last_seen_location_transliteration": en}
                )
        except AdapterError:
            log.info("last_seen_translation_skip", lang=lang)

    # Stage 4: map extraction → IntakeRecord fields.
    intake_fields = _map_extraction_to_intake(args, lang)

    # Stage 5: persist (create-or-extend).
    if intake_id is None:
        # Create path: new partial record then bulk update with
        # extracted fields.
        record = storage.create_intake_record(
            language=lang,
            source_device_id=source_device_id,
            status="partial",
        )
        before_fields: dict[str, Any] = {}
    else:
        # Extend path: read existing record, capture before-state for
        # diff, then update with extracted fields. Storage's no-op
        # detection (storage_adapter.py:168) skips unchanged fields.
        existing = storage.read_intake_record(intake_id)
        if existing is None:
            raise KeyError(f"IntakeRecord not found: {intake_id}")
        record = existing
        before_fields = {k: existing.model_dump().get(k) for k in intake_fields}

    # Filter out empty/None values that would clobber existing data
    # on the extend path. On create-path this is a no-op (all fields
    # default empty/None on the freshly-created record).
    if intake_id is not None:
        intake_fields = {
            k: v for k, v in intake_fields.items()
            if v is not None and v != "" and v != []
        }

    record = storage.update_intake_record(
        record.id,
        source_utterance=result.transcription,
        whisper_translation=result.english_translation,
        **intake_fields,
    )

    # Stage 6: structlog minor_flagged signal.
    if intake_fields.get("is_minor"):
        log.info(
            "minor_flagged",
            record_id=str(record.id),
            age=intake_fields.get("age"),
            lang=lang,
        )

    # Stage 7: matching trigger. On create-path, fire unconditionally
    # (S4 behavior). On extend-path, fire only if identity-bearing
    # fields actually changed.
    if intake_id is None:
        await _trigger_matching(record, storage=storage)
    else:
        changed = {
            k for k, v in intake_fields.items()
            if before_fields.get(k) != v
        }
        await _maybe_retrigger_matching(record, changed, storage=storage)

    # Stage 8: promote to complete if invariants satisfied.
    if record.full_name_source_script and record.relationship_to_seeker:
        if record.status != "complete":
            record = storage.update_intake_record(
                record.id, status="complete"
            )

    # Stage 9: crisis flag — fires AFTER extraction so the record is
    # fully populated when crisis_detected + referral_issued emit.
    # Returns (record, locale_message) — same tuple shape as the normal
    # path; callers that check record.is_crisis work unchanged.
    if safety.is_crisis:
        # S5 lock #4: crisis path is create-only. Guard placed here
        # (after extraction, before persistence) so a misuse doesn't
        # create a dangling populated record without the crisis flag.
        if intake_id is not None:
            raise ValueError(
                "crisis path is create-only; cannot extend "
                f"intake_id={intake_id} into a crisis turn"
            )
        # S6: invoke Gemma to format a locale-aware referral.
        # Deterministic classifier (Stage 2) is the sole safety gate;
        # Gemma's role here is structured output formatting only.
        referral_org, locale_message = await _format_crisis_referral(
            transcription=result.transcription,
            lang=lang,
            safety=safety,
            ollama=ollama,
        )
        crisis_match_path = "keyword" if safety.matched_keywords else None
        record = storage.update_intake_record(
            record.id,
            is_crisis=True,
            crisis_match_path=crisis_match_path,
            referral_issued=True,
            referral_organization=referral_org,
        )
        log.info(
            "ingest_audio_complete",
            record_id=str(record.id),
            status=record.status,
            is_crisis=record.is_crisis,
            is_minor=record.is_minor,
            lang=lang,
        )
        # Empty string fallback (Gemma tool_call failure) → None so
        # the route layer can use a clean `if message is not None`.
        return record, locale_message or None

    log.info(
        "ingest_audio_complete",
        record_id=str(record.id),
        status=record.status,
        is_crisis=record.is_crisis,
        is_minor=record.is_minor,
        lang=lang,
    )
    return record, None


# DEPRECATED: no longer called from ingest_audio after crisis-reorder.
# Crisis persistence is now handled inline in Stage 9 of ingest_audio()
# via storage.update_intake_record() on the already-extracted record.
def _persist_crisis_record(
    *,
    lang: str,
    source_device_id: str,
    safety: safety_rules.SafetyResult,
    storage: StorageAdapter,
    referral_organization: str | None = None,
) -> IntakeRecord:
    """Crisis-path persistence: create a partial record and set is_crisis
    to emit crisis_detected + referral_issued audit events. Record status
    stays partial — the worker decides when to save.

    If referral_organization is provided (S6: Gemma escalate_crisis
    output), it overrides the static _REFERRAL_ORG_BY_LANG lookup.
    Pass None (or omit) to use the static fallback — this keeps the
    pre-S6 callsite shape green and gives _format_crisis_referral
    a clean failure path.
    """
    referral_org = (
        referral_organization
        if referral_organization
        else _REFERRAL_ORG_BY_LANG.get(lang, "ICRC Family Links Network")
    )
    crisis_match_path = "keyword" if safety.matched_keywords else None

    record = storage.create_intake_record(
        language=lang,
        source_device_id=source_device_id,
        status="partial",
    )
    record = storage.update_intake_record(
        record.id,
        is_crisis=True,
        crisis_match_path=crisis_match_path,
        referral_issued=True,
        referral_organization=referral_org,
    )
    return record


# ─── Crisis referral formatting (S6) ─────────────────────────────


async def _format_crisis_referral(
    *,
    transcription: str,
    lang: str,
    safety: safety_rules.SafetyResult,
    ollama: _OllamaPort,
) -> tuple[str, str]:
    """Invoke Gemma escalate_crisis tool to format a locale-aware referral.

    Returns (referral_organization, locale_aware_message) on success;
    falls back to (_REFERRAL_ORG_BY_LANG[lang], "") on any tool_call
    or validation failure. The deterministic safety_rules.classify
    above is the SOLE safety gate; this helper only formats. See
    ADR-004 REV 2.

    Failure cannot break the safety path — the crisis flag still
    fires, the audit triple still emits, and the user still sees a
    referral organization (just templated rather than Gemma-generated).
    """
    messages = _build_crisis_messages(transcription, lang, safety.matched_keywords)
    try:
        result = await ollama.tool_call(
            messages=messages, tools=[ESCALATE_CRISIS_TOOL]
        )
        args = EscalateCrisisArgs(**result.arguments)
        log.info(
            "crisis_referral_formatted",
            referral_organization=args.referral_organization,
            locale_aware_message=args.locale_aware_message,
            lang=lang,
            matched_keyword_count=len(safety.matched_keywords),
        )
        return args.referral_organization, args.locale_aware_message
    except (
        InferenceTimeout,
        InferenceFailed,
        InvalidToolCall,
        ValidationError,
    ) as exc:
        log.warning(
            "crisis_referral_fallback",
            error_class=type(exc).__name__,
            lang=lang,
        )
        fallback = _REFERRAL_ORG_BY_LANG.get(lang, "ICRC Family Links Network")
        return fallback, ""


_TRANSLITERATION_STOPWORDS = frozenset({
    "I", "My", "The", "A", "An", "We", "He", "She", "They",
    "His", "Her", "Our", "Your", "Its", "Am", "Is", "Are",
    "Last", "With", "For", "At", "From", "Of", "No", "Not",
    "Three", "Eight", "Days", "Years", "Old", "Ago", "Gate",
    "South", "Southern", "North", "Camp", "During",
})


def _proximity_transliterate(
    arabic_name: str,
    transcription: str,
    en_candidates: list[tuple[int, str]],
    used: set[int],
    src_len: int,
    en_len: int,
) -> str | None:
    """Find the closest unused English candidate to the Arabic name's
    position in the source transcription. Returns None if not found."""
    ar_pos = transcription.find(arabic_name)
    if ar_pos == -1:
        return None
    target_en_pos = int(ar_pos / src_len * en_len)
    best_idx: int | None = None
    best_dist = float('inf')
    for idx, (en_pos, _token) in enumerate(en_candidates):
        if idx in used:
            continue
        dist = abs(en_pos - target_en_pos)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    if best_idx is None:
        return None
    used.add(best_idx)
    return en_candidates[best_idx][1]


def _fill_transliterations(
    args: ExtractIntakeFieldsArgs,
    transcription: str,
    english_translation: str,
) -> ExtractIntakeFieldsArgs:
    """Best-effort: populate all missing name transliterations — searcher,
    primary missing person, and family members — by proximity-matching
    capitalised tokens from the Whisper English translation to where each
    Arabic name appears in the source transcription.

    Covers: searcher_name_transliteration, family_member.name_transliteration.
    Only fills fields where the value is None/empty; never overwrites Gemma.
    """
    has_work = (
        (args.searcher_name and not args.searcher_name_transliteration)
        or any(m.name_transliteration is None for m in (args.family_members or []))
    )
    if not has_work:
        return args

    en_candidates: list[tuple[int, str]] = [
        (m.start(), m.group())
        for m in re.finditer(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', english_translation)
        if m.group() not in _TRANSLITERATION_STOPWORDS
    ]
    if not en_candidates:
        return args

    src_len = max(len(transcription), 1)
    en_len = max(len(english_translation), 1)
    used: set[int] = set()
    updates: dict[str, str] = {}

    # If the searcher already has a transliteration (e.g. _fill_searcher_name
    # ran first and set it), mark that candidate as used so family members
    # don't compete for it. Prevents the cascade-shift where each member
    # absorbs the next-closest English token.
    if args.searcher_name_transliteration:
        for idx, (_pos, token) in enumerate(en_candidates):
            if token == args.searcher_name_transliteration:
                used.add(idx)
                break

    # Searcher name first — it appears earliest in most transcripts.
    if args.searcher_name and not args.searcher_name_transliteration:
        t = _proximity_transliterate(
            args.searcher_name, transcription, en_candidates, used, src_len, en_len
        )
        if t:
            updates["searcher_name_transliteration"] = t

    # Family members.
    updated_members = []
    changed_members = False
    for member in (args.family_members or []):
        if member.name_transliteration is not None:
            updated_members.append(member)
            continue
        t = _proximity_transliterate(
            member.name, transcription, en_candidates, used, src_len, en_len
        )
        if t:
            updated_members.append(member.model_copy(update={"name_transliteration": t}))
            changed_members = True
        else:
            updated_members.append(member)

    if changed_members:
        updates["family_members"] = updated_members  # type: ignore[assignment]

    if not updates:
        return args
    return args.model_copy(update=updates)


async def _translate_member_marks(
    args: ExtractIntakeFieldsArgs,
    lang: str,
    *,
    ollama: _OllamaPort,
) -> ExtractIntakeFieldsArgs:
    """Backfill English distinguishing_marks_transliteration on each
    family member that has marks in source script.

    One short Gemma translate() call per member with marks. Skipped
    when the member already has a transliteration or has no marks.
    Failures (timeout, adapter error) leave the field None — the UI
    falls back to the source-script string.
    """
    if not args.family_members:
        return args

    updated: list[FamilyMemberArg] = []
    changed = False
    for member in args.family_members:
        if (
            member.distinguishing_marks
            and not member.distinguishing_marks_transliteration
        ):
            try:
                en = await ollama.translate(member.distinguishing_marks, lang)
                en = en.strip()
                if en:
                    updated.append(
                        member.model_copy(
                            update={"distinguishing_marks_transliteration": en}
                        )
                    )
                    changed = True
                    continue
            except AdapterError:
                log.info(
                    "marks_translation_skip",
                    member_name=member.name,
                    lang=lang,
                )
        updated.append(member)

    if not changed:
        return args
    return args.model_copy(update={"family_members": updated})


def _fill_searcher_name(
    args: ExtractIntakeFieldsArgs,
    transcription: str,
    english_translation: str,
) -> ExtractIntakeFieldsArgs:
    """Backfill searcher_name from English translation when Gemma missed it.

    Matches "I am [Name]" / "I'm [Name]" in the English translation,
    then proximity-matches the Latin name back to the Arabic source
    script using the same approach as _fill_transliterations(). Only
    fires when searcher_name is empty — never overwrites a good extraction.
    """
    m = re.search(
        r"\bI(?:\s+am|\s+'m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        english_translation,
    )
    if not m:
        return args

    latin_name = m.group(1)
    # Stopword guard — skip generic tokens that appear in "I am [adjective]"
    if latin_name.split()[0] in _TRANSLITERATION_STOPWORDS:
        return args

    # Find the Arabic source token at a proportional position to where
    # the English match starts, using the same proximity logic as
    # _proximity_transliterate but in reverse (English → Arabic).
    en_len = max(len(english_translation), 1)
    src_len = max(len(transcription), 1)
    en_pos = m.start(1)
    target_ar_pos = int(en_pos / en_len * src_len)

    # Arabic word tokenisation: split on whitespace, track character offsets.
    ar_tokens: list[tuple[int, str]] = []
    offset = 0
    for word in transcription.split():
        ar_tokens.append((offset, word))
        offset += len(word) + 1

    if not ar_tokens:
        return args

    best_token = min(ar_tokens, key=lambda t: abs(t[0] - target_ar_pos))[1]
    # Strip common Arabic punctuation that may attach to the token.
    best_token = best_token.strip("،؟!.،")

    updates: dict[str, str] = {
        "searcher_name": best_token,
        "searcher_name_transliteration": latin_name,
    }
    return args.model_copy(update=updates)


def _extraction_is_empty(args: ExtractIntakeFieldsArgs) -> bool:
    """True when Gemma returned no extractable identity fields.

    Checks only the fields that would populate the RecordCard roster.
    A non-empty searcher_name, full_name, or at least one family_member
    means extraction succeeded. Missing last_seen_* or marks alone is
    not considered empty — those are detail fields, not identity fields.
    """
    return (
        not args.searcher_name
        and not args.full_name
        and not args.family_members
    )


def _build_crisis_messages(
    text: str, lang: str, matched_keywords: list[str]
) -> list[dict[str, Any]]:
    """Crisis system prompt + source-language transcription as user message.

    Includes the deterministic classifier's matched_keywords inline
    so Gemma has the signal that triggered the safety branch without
    re-evaluating it. Same source-text discipline as
    _build_extraction_messages.
    """
    keyword_summary = (
        ", ".join(matched_keywords) if matched_keywords else "(none)"
    )
    user_content = (
        f"Source language: {lang}. Matched crisis keywords: "
        f"{keyword_summary}. Speaker said: {text}"
    )
    return [
        {"role": "system", "content": _CRISIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


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


_VALID_MEMBER_STATUSES: frozenset[str] = frozenset({"missing", "known", "present"})


def _map_family_members(
    members: list[FamilyMemberArg] | None,
) -> list[FamilyMember]:
    """Convert extraction-layer FamilyMemberArg list to Core FamilyMember list.

    None or empty input → empty list (Gemma returned null; no roster in
    this utterance). Status values outside the Literal set default to
    'missing' so a model hallucinating an invalid status string doesn't
    crash validation.
    """
    if not members:
        return []
    result: list[FamilyMember] = []
    for m in members:
        status = m.status if m.status in _VALID_MEMBER_STATUSES else "missing"
        result.append(
            FamilyMember(
                name=m.name,
                name_transliteration=m.name_transliteration,
                relationship_to_searcher=m.relationship_to_searcher,
                status=status,  # type: ignore[arg-type]
                age=m.age,
                last_seen_location=m.last_seen_location,
                distinguishing_marks=m.distinguishing_marks,
                distinguishing_marks_transliteration=m.distinguishing_marks_transliteration,
            )
        )
    return result


def _ensure_primary_in_roster(
    args: ExtractIntakeFieldsArgs,
) -> ExtractIntakeFieldsArgs:
    """Belt-and-suspenders: if full_name is set and not already in
    family_members, prepend it as a missing-status entry.

    Gemma may follow the schema's primary/secondary split rather than
    the prompt's instruction to list all missing persons in
    family_members. This deterministic post-processor closes the gap
    so the roster always contains every named missing person — no LLM
    variance on this invariant.

    Single-entity case (one full_name, no family_members): the primary
    is appended as the sole roster entry, which is correct — that person
    is missing and the roster is the matching surface.
    """
    if args.full_name is None:
        return args

    # Guard against Gemma conflating the searcher with the primary missing
    # person (observed on Take 4: distress-then-restate pattern caused
    # Gemma to set full_name == searcher_name). The searcher cannot be
    # missing — refuse to copy them into the roster.
    if args.searcher_name and args.full_name == args.searcher_name:
        return args

    existing_names: set[str] = {m.name for m in (args.family_members or [])}
    if args.full_name in existing_names:
        return args

    primary = FamilyMemberArg(
        name=args.full_name,
        name_transliteration=None,
        relationship_to_searcher=args.relationship or "",
        status="missing",
        age=args.age,
        last_seen_location=None,
    )
    updated = [primary, *(args.family_members or [])]
    return args.model_copy(update={"family_members": updated})


_PRESENCE_MARKERS: frozenset[str] = frozenset({
    # Arabic
    "معي", "معنا", "بجانبي", "معايا",
    # English
    "with me", "is with me", "with us", "is here", "is safe", "still with me",
})

_PRESENCE_WINDOW = 12  # characters each side of a marker to search for a name


def _detect_present_status(
    args: ExtractIntakeFieldsArgs,
    transcription: str,
) -> ExtractIntakeFieldsArgs:
    """Deterministic override for family member presence detection.

    Two passes:
    1. For each existing family_member whose name appears within
       _PRESENCE_WINDOW characters of a presence marker, override
       status → 'present'.
    2. For each presence marker, extract the nearest name-like token
       in the transcription. If that token is not already in
       family_members, add a new entry with status='present' and
       relationship inferred from the token immediately before the
       name (e.g. 'زوجتي عائشة معي' → relationship='زوجتي').

    Addresses Gemma E2B dropping present-status members entirely when
    required:status forces it to abstain rather than guess. Same
    architectural pattern as _ensure_primary_in_roster.

    Pass 1 is bidirectional: upgrades missing→present when name is near
    a marker, AND reverts present→missing when Gemma tagged present but
    the name is not near any marker in the transcription (false positive).
    """
    lower_text = transcription.lower()

    # Build (start, end) spans for every presence marker.
    marker_spans: list[tuple[int, int]] = []
    for marker in _PRESENCE_MARKERS:
        start = 0
        while True:
            pos = lower_text.find(marker.lower(), start)
            if pos == -1:
                break
            marker_spans.append((pos, pos + len(marker)))
            start = pos + 1

    def _near_marker(name: str) -> bool:
        name_lower = name.lower()
        pos = lower_text.find(name_lower)
        while pos != -1:
            name_end = pos + len(name_lower)
            for m_start, m_end in marker_spans:
                if abs(pos - m_end) <= _PRESENCE_WINDOW or abs(m_start - name_end) <= _PRESENCE_WINDOW:
                    return True
            pos = lower_text.find(name_lower, pos + 1)
        return False

    # Pass 1: bidirectional correction on existing members.
    # - missing + near marker → present
    # - present + NOT near marker → missing (revert Gemma false positive)
    # No markers in transcription at all → leave all statuses as-is.
    members: list[FamilyMemberArg] = []
    changed = False
    for member in (args.family_members or []):
        candidates = [member.name] + ([member.name_transliteration] if member.name_transliteration else [])
        near = bool(marker_spans) and any(_near_marker(c) for c in candidates)
        if member.status == "missing" and near:
            members.append(member.model_copy(update={"status": "present"}))
            changed = True
        elif member.status == "present" and marker_spans and not near:
            # Gemma tagged present but no presence marker is near this name.
            members.append(member.model_copy(update={"status": "missing"}))
            changed = True
        else:
            members.append(member)

    # Pass 2: for each marker, look for a name within the window that
    # isn't already in the member list. Extract the word(s) immediately
    # before the marker as the name candidate and the token before that
    # as a rough relationship hint.
    existing_names_lower = {m.name.lower() for m in members}
    for m_start, m_end in marker_spans:
        # Take the window of text immediately before the marker.
        window_start = max(0, m_start - _PRESENCE_WINDOW)
        window = transcription[window_start:m_start].strip()
        if not window:
            continue
        # The last word(s) before the marker are the name candidate.
        tokens = window.split()
        if not tokens:
            continue
        # Last token before the marker is the name; token before that is
        # a relationship hint (e.g. "زوجتي عائشة معي" → name="عائشة",
        # rel="زوجتي"). Single-token only: Arabic names are one word.
        candidate_name = tokens[-1]
        if candidate_name.lower() in existing_names_lower:
            continue  # already handled in pass 1
        rel_token = tokens[-2] if len(tokens) >= 2 else ""
        if len(candidate_name) >= 2:  # skip single-char noise
            members.append(FamilyMemberArg(
                name=candidate_name,
                relationship_to_searcher=rel_token,
                status="present",
            ))
            existing_names_lower.add(candidate_name.lower())
            changed = True

    if not changed:
        return args
    return args.model_copy(update={"family_members": members})


# First-person age markers in Arabic: "عمري N" / "عندي N سنة" / "أنا N سنة".
# When a digit cluster matches one of these, the age belongs to the
# searcher and must NOT be proximity-assigned to a family member.
_SEARCHER_AGE_RE = re.compile(
    r'(?:عمري|عندي|أنا)\s+(\d+)\s*سن[وة]'
)


# Arabic ordinal-word → int mapping. Used by _extract_member_ages when
# Whisper transcribes a spoken age in words rather than digits ("ثمان
# سنوات" instead of "8 سنوات"). Keyed by the longest form first so the
# regex below matches "اثنان وثلاثون" before "اثنان".
_ARABIC_WORD_NUMS: dict[str, int] = {
    # Compound 20-99
    "واحد وعشرون": 21, "اثنان وعشرون": 22, "ثلاثة وعشرون": 23,
    "اربعة وعشرون": 24, "خمسة وعشرون": 25, "ستة وعشرون": 26,
    "سبعة وعشرون": 27, "ثمانية وعشرون": 28, "تسعة وعشرون": 29,
    "واحد وثلاثون": 31, "اثنان وثلاثون": 32, "ثلاثة وثلاثون": 33,
    "اربعة وثلاثون": 34, "خمسة وثلاثون": 35, "ستة وثلاثون": 36,
    "سبعة وثلاثون": 37, "ثمانية وثلاثون": 38, "تسعة وثلاثون": 39,
    "واحد واربعون": 41, "اثنان واربعون": 42, "ثلاثة واربعون": 43,
    "اربعة واربعون": 44, "خمسة واربعون": 45,
    # Tens
    "عشرون": 20, "ثلاثون": 30, "اربعون": 40, "خمسون": 50, "ستون": 60,
    # Ones (commonly used for child ages)
    "واحد": 1, "اثنان": 2, "ثلاثة": 3, "اربعة": 4, "خمسة": 5,
    "ستة": 6, "سبعة": 7, "ثمانية": 8, "ثمان": 8, "تسعة": 9, "عشرة": 10,
}

# Regex for word-form ages following "عمره/عمرها" or preceding "سنة/سنوات".
# Group 1 captures the word-form age phrase; longest alternatives first.
_WORD_AGE_RE = re.compile(
    r'(?:عمره?ا?\s+)?(' +
    '|'.join(sorted(_ARABIC_WORD_NUMS.keys(), key=len, reverse=True)) +
    r')\s*سن[وة]'
)


def _extract_member_ages(
    args: ExtractIntakeFieldsArgs,
    transcription: str,
) -> ExtractIntakeFieldsArgs:
    """Deterministic fallback: assign each age mention to the nearest
    member name. Closest-wins prevents a distant member absorbing an
    age that belongs to a nearer one (e.g. يوسف should not absorb
    'عمره 8 سنوات' stated for محمد a few chars later).

    Only fires for members where Gemma left age=None.

    Searcher's own age ("عمري N سنة") is excluded from the pool so it
    cannot leak onto the nearest family member via proximity matching.
    """
    if not args.family_members:
        return args

    # Collect all age mentions as (start_pos, age_value) tuples. Two
    # sources: digit-form ("8 سنوات") and word-form ("ثمان سنوات").
    age_hits: list[tuple[int, int]] = []
    # Digit form: "عمره N" or "N سنة/سنوات"
    for m in re.finditer(r'(?:عمره?\s+)?(\d+)\s*سن[وة]', transcription):
        age_hits.append((m.start(), int(m.group(1))))
    # Word form: Whisper transcribes some speakers in Arabic words.
    for m in _WORD_AGE_RE.finditer(transcription):
        age_hits.append((m.start(), _ARABIC_WORD_NUMS[m.group(1)]))

    if not age_hits:
        return args

    # Collect character offsets of the DIGIT GROUP within each searcher
    # age mention so we can compare against age_match.start() directly.
    # _SEARCHER_AGE_RE uses group(1) for the digit; m.start(1) is the
    # offset of the digits inside "عمري 41 سنة" — same position that
    # the broader age_mentions regex reports as its match start.
    searcher_age_offsets: set[int] = {
        m.start(1) for m in _SEARCHER_AGE_RE.finditer(transcription)
    }
    # Searcher word-age offsets (e.g. "عمري واحد واربعون سنة").
    for m in re.finditer(
        r'(?:عمري|عندي|أنا)\s+(' +
        '|'.join(sorted(_ARABIC_WORD_NUMS.keys(), key=len, reverse=True)) +
        r')\s*سن[وة]',
        transcription,
    ):
        searcher_age_offsets.add(m.start(1))

    updated = list(args.family_members)
    changed = False

    for age_pos, age_val in age_hits:
        if age_pos in searcher_age_offsets:
            continue  # searcher's own age — skip

        # Find the closest member by name position across ALL members,
        # whether or not they already have an age. If the closest member
        # already has an age, this age is bound to them — don't fall
        # through to a more distant member (that would leak ages to
        # bystanders, e.g. assign Mohammed's '8' to Aisha just because
        # Aisha is the next-closest member without an age).
        best_idx: int | None = None
        best_dist = float('inf')
        for i, member in enumerate(updated):
            for name_match in re.finditer(re.escape(member.name), transcription):
                dist = abs(name_match.start() - age_pos)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

        # Skip if the closest member already has an age (consumed).
        if best_idx is not None and updated[best_idx].age is not None:
            continue

        if best_idx is not None and best_dist < 40:
            updated[best_idx] = updated[best_idx].model_copy(
                update={"age": age_val}
            )
            changed = True

    if not changed:
        return args
    return args.model_copy(update={"family_members": updated})


def _promote_first_missing_to_primary(
    args: ExtractIntakeFieldsArgs,
) -> ExtractIntakeFieldsArgs:
    """Fallback: when Gemma leaves full_name null but family_members has
    missing-status entries, promote the first missing member to full_name.

    Prevents 'null' rendering in the UI record card when the model puts
    everyone in family_members and omits the primary slot. The promoted
    member stays in family_members too — _to_rfl_record filters the
    primary from the matching-view roster to prevent double-counting.
    """
    if args.full_name is not None:
        return args
    if not args.family_members:
        return args
    first_missing = next(
        (m for m in args.family_members if m.status == "missing"), None
    )
    if first_missing is None:
        return args
    return args.model_copy(update={
        "full_name": first_missing.name,
        "relationship": first_missing.relationship_to_searcher or args.relationship,
    })


# Arabic location prepositions that introduce a place reference.
# Word-boundary anchored so a clitic 'ب' attached to another token
# (e.g. 'قبل' "before") does not match. Capturing group 2 is the
# place name span (optional 'ال' article kept in group 1).
_AR_LOCATION_PREP_RE = re.compile(
    r'(?:^|\s)(عند|في|داخل|قرب|جنب|على)\s+((?:ال)?[؀-ۿ]+(?:\s+(?!قبل|منذ|بعد)[؀-ۿ]+){0,2})'
)

# Arabic time/date phrases that introduce a temporal reference:
#   قبل N أيام/يوم/أسبوع/شهر/سنة   "N days/weeks/months/years ago"
#   قبل أسبوع                       "a week ago" (no number)
#   منذ ...                          "since ..."
_AR_DATE_RE = re.compile(
    r'((?:قبل|منذ)\s+'
    r'(?:(?:\d+|واحد|اثنان|ثلاثة|اربعة|خمسة|ستة|سبعة|ثمان(?:ية)?|تسعة|عشرة)\s+)?'
    r'(?:يوم|أيام|أسبوع|أسابيع|شهر|أشهر|سنة|سنوات))'
)


def _split_location_from_circumstance(
    args: ExtractIntakeFieldsArgs,
) -> ExtractIntakeFieldsArgs:
    """Backstop: when Gemma bundled location/date inside
    separation_circumstance, split them into the dedicated fields.

    Only fires when (a) separation_circumstance is set, (b) at least
    one of last_seen_location / last_seen_date is empty, and (c) the
    Arabic prep/date regex finds a candidate inside the circumstance
    string. Idempotent — running twice yields the same result.
    """
    circ = args.separation_circumstance
    if not circ:
        return args
    if args.last_seen_location and args.last_seen_date:
        return args

    updates: dict[str, Any] = {}
    circ_remaining = circ

    if not args.last_seen_location:
        loc_match = _AR_LOCATION_PREP_RE.search(circ)
        if loc_match:
            # group(1) = preposition, group(2) = place-name span (with
            # optional 'ال' article preserved).
            place_full = loc_match.group(2).strip()
            # Heuristic guard: short tokens (< 3 chars) are unlikely to
            # be a real place name; skip.
            if len(place_full) >= 3:
                updates["last_seen_location"] = place_full
                circ_remaining = (
                    circ_remaining[: loc_match.start()].strip()
                    + " "
                    + circ_remaining[loc_match.end():].strip()
                ).strip()

    if not args.last_seen_date:
        date_match = _AR_DATE_RE.search(circ_remaining)
        if date_match:
            updates["last_seen_date"] = date_match.group(1).strip()
            circ_remaining = (
                circ_remaining[: date_match.start()].strip()
                + " "
                + circ_remaining[date_match.end():].strip()
            ).strip()

    # If we extracted anything, also clean up the residual circumstance.
    if updates:
        # If only the verb stub remains (e.g. just "فقدنا"), keep it;
        # otherwise normalize whitespace.
        circ_remaining = " ".join(circ_remaining.split())
        if circ_remaining and circ_remaining != circ:
            updates["separation_circumstance"] = circ_remaining or None

    if not updates:
        return args
    return args.model_copy(update=updates)


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
    # On extend turns Gemma may emit null for fields the speaker
    # didn't repeat. The pipeline's empty-filter (extend path) drops
    # None / "" entries so existing data is preserved. On create
    # path, IntakeRecord requires str (not None) for the identity
    # fields; coerce None → "" here so validation succeeds and
    # storage's no-op detection treats the empty as "not yet set."
    full_name = args.full_name
    relationship = args.relationship
    is_latin = lang in _LATIN_SCRIPT_LANGS
    # record.age semantically holds the PRIMARY MISSING PERSON's age —
    # consumed by _to_rfl_record → matching as the missing person's age.
    # args.age per the tool schema is the SEARCHER's age, so we source
    # the primary's age from family_members[primary] instead.
    primary_age: int | None = None
    if full_name and args.family_members:
        primary_member = next(
            (m for m in args.family_members if m.name == full_name),
            None,
        )
        if primary_member is not None:
            primary_age = primary_member.age
    # is_minor fires when the SEARCHER is under 18, OR when any MISSING
    # family member is under 18 — the child-protection flag must cover
    # both cases. Searcher-age check guards the unaccompanied-minor case;
    # family-member check guards the "lost child" case (Mohamad, age 8).
    searcher_minor = args.age is not None and args.age < 18
    member_minor = any(
        m.age is not None and m.age < 18 and m.status != "present"
        for m in (args.family_members or [])
    )
    is_minor = searcher_minor or member_minor

    return {
        "full_name_source_script": full_name if full_name is not None else "",
        "full_name_transliteration": (
            full_name if (full_name is not None and is_latin) else ""
        ),
        "relationship_to_seeker": (
            relationship if relationship is not None else ""
        ),
        "age": primary_age,
        "is_minor": is_minor,
        "last_seen_location": args.last_seen_location,
        "last_seen_location_transliteration": args.last_seen_location_transliteration,
        "last_seen_date": args.last_seen_date,
        # IntakeRecord uses `distinguishing_marks`; the extraction
        # tool's idiom is `distinguishing_features`. Names diverge
        # historically but mean the same thing.
        "distinguishing_marks": args.distinguishing_features,
        "separation_circumstance": args.separation_circumstance,
        "searcher_name": (
            args.searcher_name if args.searcher_name is not None else ""
        ),
        "searcher_name_transliteration": (
            args.searcher_name_transliteration
            if args.searcher_name_transliteration is not None
            else ""
        ),
        "searcher_relationship_to_target": (
            args.searcher_relationship_to_target
            if args.searcher_relationship_to_target is not None
            else ""
        ),
        "family_roster": _map_family_members(args.family_members),
    }


# ─── Matching trigger (S5) ───────────────────────────────────────


# IntakeRecord field names that, when changed by an extend turn or a
# worker-entered transliteration update, must re-fire matching.
# `relationship_to_seeker` is excluded because matching.py does not
# consume it (verified S5 recon Q6); changes to it can't affect match
# outcomes. `is_minor` excluded for the same reason.
_IDENTITY_FIELDS_FOR_MATCHING = frozenset({
    "full_name_source_script",
    "full_name_transliteration",
    "age",
    "last_seen_location",
    "last_seen_date",
    "distinguishing_marks",
})


async def _maybe_retrigger_matching(
    record: IntakeRecord,
    changed_fields: set[str],
    *,
    storage: StorageAdapter,
) -> list[MatchLink]:
    """Fire _trigger_matching only when changed fields could affect
    a match outcome. Used by the extend path of ingest_audio and the
    POST /intake/{id}/transliteration route.

    Returns the list of MatchLinks created (possibly empty).
    """
    relevant = changed_fields & _IDENTITY_FIELDS_FOR_MATCHING
    if not relevant:
        return []
    log.info(
        "matching_retrigger_fired",
        record_id=str(record.id),
        changed_fields=sorted(relevant),
    )
    return await _trigger_matching(record, storage=storage)


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

    # Exclude the primary missing person from the roster passed to the
    # matcher — they are already covered by RFLRecord.name (missing_person
    # slot). Keeping them in both slots causes match_records_network to
    # fire duplicate NodeMatch pairs (path 2 + path 6 both match the same
    # name). Storage (IntakeRecord.family_roster) is unaffected; this
    # filter only applies to the matching view.
    primary_name = intake.full_name_source_script
    matching_roster = [
        m for m in intake.family_roster if m.name != primary_name
    ] if primary_name else intake.family_roster

    return RFLRecord(
        name=name,
        age=age,
        relationship=intake.relationship_to_seeker or None,
        last_seen=last_seen,
        guardian=Guardian(present=False, consent=False),
        distinguishing_marks=marks,
        family_roster=matching_roster,
        searcher_name=intake.searcher_name or None,
        searcher_name_transliteration=(
            intake.searcher_name_transliteration or None
        ),
        searcher_relationship_to_target=(
            intake.searcher_relationship_to_target or None
        ),
    )


async def _trigger_matching(
    new_record: IntakeRecord,
    *,
    storage: StorageAdapter,
) -> list[MatchLink]:
    """Fan-out matching: pairwise match_records vs every eligible
    candidate; persist hits as proposed MatchLinks.

    Filters:
      - drop self (don't self-match)
      - all records (complete, partial, crisis-flagged) enter the pool

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
    candidates = [r for r in all_records if r.id != new_record.id]

    new_rfl = _to_rfl_record(new_record)

    # Two-pass: first collect all matches so we know the run total,
    # then emit each with candidate_count = total. Bundle 1.5 S5
    # requires every match_proposed event to carry the run-level
    # candidate count so the frontend state can derive the queue
    # rail badge value without re-counting events.
    matches: list[tuple[IntakeRecord, MatchResult, NetworkMatchResult]] = []
    for candidate in candidates:
        candidate_rfl = _to_rfl_record(candidate)
        same_role = match_records(new_rfl, candidate_rfl)
        network = match_records_network(new_rfl, candidate_rfl)
        if same_role.is_match or network.matched:
            matches.append((candidate, same_role, network))

    created_links: list[MatchLink] = []
    if matches:
        candidate_count = len(matches)
        for candidate, same_role, network in matches:
            # Confidence band: same-role wins ties; cross-role provides
            # evidence when same-role alone did not match.
            if same_role.is_match and (
                not network.matched
                or same_role.score
                >= network.primary_match.composite_score  # type: ignore[union-attr]
            ):
                conf_band = same_role.confidence
                conf_score = same_role.score
            else:
                pm = network.primary_match
                assert pm is not None  # network.matched=True guarantees this
                conf_band = confidence_band_for_score(
                    pm.phonetic_score,
                    pm.phonetic_score == 1.0,
                    0,
                    pm.composite_score,
                )
                conf_score = pm.composite_score

            match_reasoning = {
                # Existing keys preserved for backward compat:
                "matched_fields": list(same_role.matched_fields),
                "phonetic_score": same_role.phonetic_score,
                "reason": same_role.reason,
                # New key — None when only same-role fired:
                "network_match": network.model_dump() if network.matched else None,
            }
            # ORDERING CONVENTION (Bundle 1.5 S5): record_a_id is
            # ALWAYS the new record being matched; record_b_id is the
            # candidate counterparty. Downstream consumers (frontend
            # match-candidate state, audit-event filters) depend on
            # record_ids[0] being the new record. Do not swap without
            # updating src/ui/web/src/state/matchCandidates.ts.
            link = storage.create_match_link(
                record_a_id=new_record.id,
                record_b_id=candidate.id,
                confidence_band=conf_band,
                confidence_score=conf_score,
                match_reasoning=match_reasoning,
                candidate_count=candidate_count,
                details={
                    "network_match": (
                        network.model_dump() if network.matched else None
                    ),
                },
            )
            created_links.append(link)
    else:
        # Bundle 1.5 S5: always-emit on zero-result runs so the
        # frontend matchCandidates state can confirm "this turn
        # produced no candidates" rather than guessing from event
        # absence. Single summary event with record_ids=[new_record_id]
        # and candidate_count=0.
        storage.emit_match_proposed_empty(new_record_id=new_record.id)

    log.info(
        "matching_trigger_fired",
        new_record_id=str(new_record.id),
        candidate_count=len(candidates),
        match_count=len(created_links),
    )
    return created_links
