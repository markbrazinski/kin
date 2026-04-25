# audio_samples/

Phase 2.5 evaluation samples — the audio clips used to probe
Gemma 4 E2B's multilingual audio-input capability in April 2026.
This directory is gitignored (except for this README); samples
are not redistributed with the repo.

## The locked language set (per PROJECT_PLAN.md §3)

KIN ships with four languages: **English, Spanish, Arabic, Farsi**.
All other samples in this directory are Phase 2.5 evaluation
artifacts kept only as reference for `docs/test_strategy.md`
findings. Do not wire out-of-scope samples into tests — they are
not part of the supported surface.

## Inventory

| Language   | Count | In scope? | Notes                                 |
|------------|------:|-----------|---------------------------------------|
| English    |     4 | ✅        | incl. human-voice and padded variants |
| Spanish    |     3 | ✅        |                                       |
| Arabic     |     7 | ✅        | mix of .wav and .mp3                  |
| Farsi      |     1 | ✅        |                                       |
| Amharic    |     1 | ❌ ref.   | Phase 2.5 ruled out                   |
| Bengali    |     3 | ❌ ref.   | Phase 2.5 ruled out                   |
| French     |     4 | ❌ ref.   | Phase 2.5 ruled out                   |
| Portuguese |     3 | ❌ ref.   | Phase 2.5 ruled out                   |
| Swahili    |     8 | ❌ ref.   | see callout below — do NOT delete     |
| Tigrinya   |     6 | ❌ ref.   | mix of .wav and .mp3                  |
| Ukrainian  |     9 | ❌ ref.   | mix of .wav and .mp3                  |

Counts are directory-listing at session landing; files may change
as probes re-run.

## Swahili callout

The Swahili clips are the provenance for the 39-minute
runaway-loop evidence cited in CLAUDE.md ("Learned audio pipeline
constraints" §4) and `docs/test_strategy.md`. That finding is
load-bearing for the adapter 25s timeout decision. If these
samples are removed, the evidence for a key §9 risk-mitigation
finding is lost. Keep them.

## `audio_samples/` vs `tests/fixtures/`

- **`audio_samples/`** — Phase 2.5 raw probe inputs. Not used by
  the test suite. Gitignored.
- **`tests/fixtures/`** — captured Gemma responses for
  deterministic tests. Populated Day 5-7 per PROJECT_PLAN §6.5,
  when prompts stabilize. Committed.
