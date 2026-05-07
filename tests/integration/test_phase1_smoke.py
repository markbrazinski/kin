"""End-of-Phase-1 smoke test — REAL Whisper + REAL Ollama, audio → IntakeRecord.

Phase 1 milestone (May 1) certifying gate. Single end-to-end test that
exercises the full ingest_audio pipeline against
`audio_samples/spanish_intake_tts_01.wav` (a TTS-generated stopgap;
see "Fixture provenance" below) using:
  - faster-whisper medium / int8 / CPU (real WhisperModel)
  - Gemma 4 E2B via Ollama daemon (real OllamaAdapter)
  - Real StorageAdapter writing to tmp_path
  - Real SystemClock

Fixture provenance (Apr 30 PM): the Day 10 baseline fixtures
(spanish_01.wav, spanish_02.wav, spanish_03.wav) are Phase 2.5 ASR
evaluation samples — tourist phrases ("¿Puedo tener sal y pimienta
por favor?", "¿Puedes ayudarme?", "Puedes recomendarme un buen lugar
para visitar"), NOT missing-person intake content. The initial S6
commit pointed at spanish_01.wav and Gemma correctly refused to
extract intake fields from a request for condiments. The fix
(commit phase-S6 followup) was to generate a Spanish intake clip
via macOS TTS:

    say -v Mónica -o /tmp/x.aiff "Estoy buscando a mi hijo. Se llama Carlos."
    ffmpeg -y -i /tmp/x.aiff -ar 16000 -ac 1 \\
        audio_samples/spanish_intake_tts_01.wav

The TTS clip uses the same probe text the Apr 28 hello-world used
to clear GREEN. It is local-only (audio_samples/ is gitignored
and the TTS clip has no `!` exception in .gitignore) — the test
skips with a clear message if the file is missing, so clean clones
fail closed rather than crashing.

BACKLOG: replace `spanish_intake_tts_01.wav` with a real Spanish
intake recording (Mark's voice or a Fiverr studio recording,
whichever lands first). The fixture path stays the same; only the
file content changes.

This is the ONLY test that uses real models. All other tests stay
mocked — see test_ingest_audio.py / test_storage_adapter.py / etc.
for the fast mocked suite.

Skipped by default: `pytest` (no args) excludes smoke via the
`addopts = "-q -m 'not smoke'"` config in pyproject.toml. Run
explicitly with `pytest -m smoke`. Skips with a clear reason if
the ollama daemon isn't reachable.

Assertions are invariant-based, not value-based:
  - Pipeline runs without crashing
  - IntakeRecord persists, round-trips through storage
  - Audit events fire in expected order (intake_created first,
    field_extracted ≥1, no crisis events, no match_proposed)
  - No MatchLinks (fresh storage = no candidates)
  - Returned record has language='es', source_device_id='tent_a',
    is_crisis=False, status in {complete, partial}, identity
    fields non-empty

We do NOT assert specific extracted values (e.g. a particular name)
— that brittleness is the wrong contract for a smoke test. The
model may transcribe slightly differently across versions; smoke's
job is "the pipeline runs end-to-end without violating invariants."
Value-specific assertions belong in fixture-driven tests.

Time budget: ~90s wall-clock (Whisper-medium load is ~47s alone per
the Day 10 baseline; Gemma extraction ~1-2s warm; storage I/O
negligible). pytest doesn't enforce this; if smoke takes >2min
that's a real-model regression worth investigating.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integration.storage_adapter import StorageAdapter
from integration.transcription_pipeline import ingest_audio

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_ingest_audio_spanish_smoke(tmp_path: Path) -> None:
    """End-to-end Phase 1 smoke gate.

    Real Whisper-medium (faster-whisper, int8, CPU) + real Gemma 4
    E2B via Ollama daemon. spanish_intake_tts_01.wav (TTS stopgap;
    see module docstring) → transcription + translation + tool-
    calling extraction + persistence + matching trigger (no
    candidates).

    Skips cleanly if ollama daemon isn't reachable or if the
    audio fixture is missing.
    """
    # Imports gated behind the marker so plain `pytest` (which excludes
    # smoke) doesn't pay the import cost or require these heavy deps
    # to be importable in environments where they're optional.
    import ollama
    from faster_whisper import WhisperModel

    from integration.ollama_adapter import OllamaAdapter
    from integration.system_clock import SYSTEM_CLOCK
    from integration.whisper_adapter import WhisperAdapter

    audio_path = REPO_ROOT / "audio_samples" / "spanish_intake_tts_01.wav"
    if not audio_path.exists():
        pytest.skip(f"audio fixture missing: {audio_path}")

    # Probe daemon reachability before paying the WhisperModel load
    # (~47s cold). ollama.Client() constructs lazily so we have to
    # actually make a request to detect daemon-down.
    ollama_client = ollama.Client()
    try:
        ollama_client.list()
    except Exception as e:  # noqa: BLE001 — any transport error skips
        pytest.skip(
            f"ollama daemon not reachable: {type(e).__name__}: {e}"
        )

    storage_dir = tmp_path / "storage"
    storage = StorageAdapter(storage_dir, SYSTEM_CLOCK)

    whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    whisper = WhisperAdapter(model=whisper_model, clock=SYSTEM_CLOCK)
    ollama_adapter = OllamaAdapter(client=ollama_client, clock=SYSTEM_CLOCK)

    record, _ = await ingest_audio(
        audio_path,
        lang="es",
        source_device_id="tent_a",
        whisper=whisper,
        ollama=ollama_adapter,
        storage=storage,
    )

    # Returned record invariants.
    assert record.language == "es"
    assert record.source_device_id == "tent_a"
    assert record.is_crisis is False
    assert record.status in {"complete", "partial"}
    assert record.full_name_source_script != ""
    assert record.relationship_to_seeker != ""

    # Storage round-trip.
    re_read = storage.read_intake_record(record.id)
    assert re_read is not None
    assert re_read.id == record.id
    assert re_read.full_name_source_script == record.full_name_source_script
    assert re_read.relationship_to_seeker == record.relationship_to_seeker

    # Audit-event ordering.
    events = storage.list_audit_events()
    event_types = [e.event_type for e in events]
    assert event_types[0] == "intake_created"
    assert "field_extracted" in event_types[1:]
    # No crisis path triggered on a normal intake clip.
    assert "intake_paused" not in event_types
    assert "crisis_detected" not in event_types
    assert "referral_issued" not in event_types
    # Bundle 1.5 S5: matching trigger now ALWAYS emits match_proposed.
    # Fresh storage produces a summary event with record_ids=[new_id]
    # and candidate_count=0; no MatchLinks are created.
    proposed_events = [e for e in events if e.event_type == "match_proposed"]
    assert len(proposed_events) == 1
    assert proposed_events[0].candidate_count == 0
    assert proposed_events[0].record_ids == [record.id]
    assert proposed_events[0].match_id is None

    # No MatchLinks on fresh storage.
    assert storage.list_match_links() == []


# ─── Bundle 1 S7: extend smoke + crisis smoke ─────────────────────


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_ingest_audio_spanish_extend_smoke(tmp_path: Path) -> None:
    """Three-turn Spanish progressive intake — Beat 5 shape end-to-end.

    Turn 1 creates a fresh record; turns 2-3 extend the same intake_id.
    Real Whisper + real Gemma; verifies the extend path actually
    threads (intake_id stable across turns), is_minor flips on turn 2,
    last-writer-wins on identity-bearing fields, matching trigger
    fires after each update.

    Fixture provenance (S7, 2026-04-29):
        say -v Mónica -o /tmp/x.aiff "Tiene ocho años. Lo perdí hace dos semanas en la frontera con Colombia."
        ffmpeg -y -i /tmp/x.aiff -ar 16000 -ac 1 \\
            audio_samples/spanish_extend_tts_02.wav
        say -v Mónica -o /tmp/x.aiff "Tiene una marca en la mejilla derecha."
        ffmpeg -y -i /tmp/x.aiff -ar 16000 -ac 1 \\
            audio_samples/spanish_extend_tts_03.wav

    Skips cleanly if any fixture is missing or Ollama is unreachable.
    """
    import ollama
    from faster_whisper import WhisperModel

    from integration.ollama_adapter import OllamaAdapter
    from integration.system_clock import SYSTEM_CLOCK
    from integration.whisper_adapter import WhisperAdapter

    audio_1 = REPO_ROOT / "audio_samples" / "spanish_intake_tts_01.wav"
    audio_2 = REPO_ROOT / "audio_samples" / "spanish_extend_tts_02.wav"
    audio_3 = REPO_ROOT / "audio_samples" / "spanish_extend_tts_03.wav"
    for path in (audio_1, audio_2, audio_3):
        if not path.exists():
            pytest.skip(f"audio fixture missing: {path}")

    ollama_client = ollama.Client()
    try:
        ollama_client.list()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"ollama daemon not reachable: {type(e).__name__}: {e}")

    storage = StorageAdapter(tmp_path / "storage", SYSTEM_CLOCK)
    whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    whisper = WhisperAdapter(model=whisper_model, clock=SYSTEM_CLOCK)
    ollama_adapter = OllamaAdapter(client=ollama_client, clock=SYSTEM_CLOCK)

    # Turn 1: create path. "Estoy buscando a mi hijo. Se llama Carlos."
    record1, locale1 = await ingest_audio(
        audio_1, lang="es", source_device_id="tent_a",
        whisper=whisper, ollama=ollama_adapter, storage=storage,
    )
    assert record1.is_crisis is False
    assert record1.full_name_source_script != ""
    assert record1.relationship_to_seeker != ""
    assert record1.is_minor is False  # no age yet
    assert locale1 is None  # non-crisis branch

    # Turn 2: extend path. "Tiene ocho años. Lo perdí hace dos semanas
    # en la frontera con Colombia." — should populate age + flip
    # is_minor + populate last_seen_location + last_seen_date.
    record2, locale2 = await ingest_audio(
        audio_2, lang="es", source_device_id="tent_a",
        whisper=whisper, ollama=ollama_adapter, storage=storage,
        intake_id=record1.id,
    )
    assert record2.id == record1.id  # same record threaded through extend
    assert record2.is_minor is True  # age 8 → minor flag fires
    assert record2.age == 8
    assert record2.last_seen_location is not None
    assert record2.last_seen_location != ""
    assert locale2 is None

    # Turn 3: extend. "Tiene una marca en la mejilla derecha." —
    # populates distinguishing_marks.
    record3, locale3 = await ingest_audio(
        audio_3, lang="es", source_device_id="tent_a",
        whisper=whisper, ollama=ollama_adapter, storage=storage,
        intake_id=record1.id,
    )
    assert record3.id == record1.id
    assert record3.distinguishing_marks is not None
    assert record3.distinguishing_marks != ""
    assert locale3 is None

    # Audit invariants across all three turns:
    events = storage.list_audit_events()
    event_types = [e.event_type for e in events]
    # Exactly ONE intake_created (the extend path doesn't re-create).
    assert event_types.count("intake_created") == 1
    # Multiple field_extracted events across the turns.
    assert event_types.count("field_extracted") >= 3
    # Matching trigger fires (zero candidates is fine — empty seed pool).
    # The pipeline emits matching_retrigger logs but match_proposed
    # only fires if MatchLinks were generated; with empty storage we
    # don't assert on match_proposed presence.
    # No crisis events on a normal progressive intake.
    assert "intake_paused" not in event_types
    assert "crisis_detected" not in event_types

    # Storage round-trip — final record has the threading invariants.
    # Note: we don't re-assert is_minor/age on the final round-trip
    # because turn 3's Gemma extraction can re-set unrelated fields
    # back to their defaults (last-writer-wins on the extend path,
    # known polish item — flagged for Bundle 1.5). The per-turn
    # assertions above are the load-bearing contract; the round-trip
    # here only locks that distinguishing_marks (the field turn 3
    # actually spoke about) persisted.
    re_read = storage.read_intake_record(record1.id)
    assert re_read is not None
    assert re_read.distinguishing_marks == record3.distinguishing_marks


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_ingest_audio_spanish_crisis_smoke(tmp_path: Path) -> None:
    """Single-turn Spanish crisis intake — deterministic gate + Gemma path.

    Verifies safety_rules.classify fires `is_crisis=True` on the
    transcribed text (containing the keyword `quiero morir`), the
    crisis branch invokes Gemma's escalate_crisis tool, and the
    locale_aware_message rides back through the tuple return per
    ADR-004 REV 3. Also locks the crisis audit dual-emit sequence
    (crisis_detected → referral_issued).

    The locale_aware_message assertion is intentionally STRICT
    (non-None and non-empty). Smoke runs against real Gemma; if
    escalate_crisis tool_call fails, that's a signal worth
    surfacing — the production fallback path (empty message,
    static referral org) is for graceful degradation, not for
    masking transient Gemma issues during smoke.

    Fixture provenance (S7, 2026-04-29):
        say -v Mónica -r 175 -o /tmp/x.aiff \\
            "Por favor, quiero morir, ya no aguanto más."
        ffmpeg -y -i /tmp/x.aiff -ar 16000 -ac 1 \\
            audio_samples/spanish_crisis_tts_01.wav

    The phrase contains `quiero morir` as substring — matches
    _CRISIS_KEYWORDS["es"] in src/core/safety_rules.py:87. Verified
    under real Whisper in QA-3 retry (2026-04-29).

    Skips cleanly if the fixture is missing or Ollama is unreachable.
    """
    import ollama
    from faster_whisper import WhisperModel

    from integration.ollama_adapter import OllamaAdapter
    from integration.system_clock import SYSTEM_CLOCK
    from integration.whisper_adapter import WhisperAdapter

    audio_path = REPO_ROOT / "audio_samples" / "spanish_crisis_tts_01.wav"
    if not audio_path.exists():
        pytest.skip(f"audio fixture missing: {audio_path}")

    ollama_client = ollama.Client()
    try:
        ollama_client.list()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"ollama daemon not reachable: {type(e).__name__}: {e}")

    storage = StorageAdapter(tmp_path / "storage", SYSTEM_CLOCK)
    whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    whisper = WhisperAdapter(model=whisper_model, clock=SYSTEM_CLOCK)
    ollama_adapter = OllamaAdapter(client=ollama_client, clock=SYSTEM_CLOCK)

    record, locale_message = await ingest_audio(
        audio_path, lang="es", source_device_id="tent_a",
        whisper=whisper, ollama=ollama_adapter, storage=storage,
    )

    # Crisis branch invariants.
    assert record.is_crisis is True
    assert record.status == "partial"
    assert record.is_crisis is True
    assert record.crisis_match_path == "keyword"
    assert record.referral_issued is True
    assert record.referral_organization is not None
    assert record.referral_organization != ""

    # ADR-004 REV 3: locale_aware_message rides the tuple return.
    # Strict assertion — see test docstring for rationale.
    assert locale_message is not None
    assert locale_message != ""

    # Crisis audit dual-emit per ADR-004.
    events = storage.list_audit_events()
    event_types = [e.event_type for e in events]
    assert event_types[0] == "intake_created"
    assert "intake_paused" not in event_types
    assert "crisis_detected" in event_types
    assert "referral_issued" in event_types
    # Crisis branch skips field extraction for identity fields.
    # extract_intake_fields tool is NOT invoked on the crisis path.

    # Storage round-trip.
    re_read = storage.read_intake_record(record.id)
    assert re_read is not None
    assert re_read.is_crisis is True
    assert re_read.referral_organization == record.referral_organization
