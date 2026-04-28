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

    record = await ingest_audio(
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
    # Fresh storage → matching trigger fires but produces no MatchLinks.
    assert "match_proposed" not in event_types

    # No MatchLinks on fresh storage.
    assert storage.list_match_links() == []
