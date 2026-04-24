# KIN Decisions Log

Append-only. Each entry dated. Do not edit past entries; add new
ones that supersede if a decision reverses.

## 2026-04-22: Language reliability threshold for demo inclusion
A language is "in the demo" if semantic match on core fields
(name, age, distinguishing detail) succeeds on 2 of 3 probe runs
at temp=0.1 on a clean Common Voice clip. 1 of 3 or 0 of 3 →
"pathway to more" list, not demoed.

## 2026-04-22: Phase 2.5 timebox
Phase 2.5 exits at end of next work session regardless of sweep
completeness. If fewer than 5 languages pass the threshold by
that point, move to Phase 4 with the languages that passed and
adjust the writeup's language claims accordingly.

## 2026-04-22: Gemma 3n E2B ruled out as audio fallback
Fabricates on audio. Not a backup. See CLAUDE.md learned
constraints section.

## 2026-04-23: Final demo language lock — 4 languages

After Phase 2.5 sweep (32 total probes across 9 candidate languages),
KIN demos in: English, Spanish, Arabic, Farsi.

Out with evidence: Ukrainian (0/6 across FLEURS + Common Voice),
French (0/4), Portuguese (0/3), Bengali (0/3), Swahili (0/8),
Tigrinya (0/3), Amharic (0/3).

Pattern: Gemma 4 E2B's audio encoder reliably handles the highest-
resource languages in its pretraining distribution. Text-model
knowledge of a language does not predict audio-encoder capability
for that language. This is a model-level constraint we document
and live with.

## 2026-04-23: Integration-layer invariants flagged for Phase 4

Audio padding and inference timeout are currently implemented per-caller
(run_three_tests.py, farsi_retest.py, fetch_*.py, test_audio_smoke.py)
rather than centrally. This is a known inconsistency that should be
resolved in the Phase 4 Integration layer by extracting an ollama_adapter
module that wraps every Gemma call with canonical padding + timeout +
logging. probe_audio.py itself has neither invariant currently — safe
for controlled experiments, not safe for production paths.

## 2026-04-23: Multi-turn coherence probe — Tier 2 locks

Probe: 12 trials (2 langs × 3 trials × 2 variants), 3 turns each.
Result: 12/12 pass. No field clobbering across 36 turns.
  - Farsi: 3/3 unconstrained, 3/3 constrained
  - Arabic: 3/3 unconstrained, 3/3 constrained
  - Delta: 0 — format=<schema> not load-bearing for coherence

Key fix from first run: FIELD SEMANTICS block clarifying full_name
(missing person) vs seeker_name (speaker). Prompt underspecification,
not model capability, caused the first-run failures.

Decisions:
1. Tier 2 architecture LOCKED. update_rfl_record multi-turn is safe.
2. format=<schema> REMAINS an Integration-layer parameter in
   ollama_adapter. Not mandatory for coherence but cheap insurance
   against malformed output reaching Pydantic + Jones-Bell-calibrated
   schema safety.
3. OPEN: constrained-mode translation drift on Farsi (location, date
   fields emitted in English instead of source language). Mitigation
   is a "preserve source language" instruction in the ollama_adapter
   system prompt. Test in Phase 5 fixture suite.