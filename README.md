# KIN

**Offline voice intake for family reunification in displacement settings.**

`5,770 lines Python` · `10,836 lines TypeScript` · `~311 tests` · `6 languages` · `fully offline`

![Architecture](docs/architecture-diagram.png)

---

## What it does

KIN takes a voice note from a displaced person, transcribes it with faster-whisper, runs a crisis safety check, then calls Gemma 4 E2B via Ollama's native tool-calling interface to extract structured intake fields (names, relationships, ages, last-known locations, distinguishing features). Extracted records are matched against a local JSONL queue using phonetic similarity scoring. Every inference produces an append-only audit event. The entire pipeline runs on a single laptop — no network connection, no API keys, no cloud calls.

Supports 6 languages (EN / ES / AR / FA / FR / UK). Four are demoed end-to-end: English, Spanish, Arabic, Farsi.

---

## Gemma 4 E2B

This is the primary integration point judges should verify.

**Model:** `gemma4:e2b` — hardcoded in [`src/integration/ollama_adapter.py:59`](src/integration/ollama_adapter.py). E2B (~2.3B effective parameters, ~3–5 GiB at Q4) was chosen specifically to fit on a 5-to-10-year-old laptop with 8–16 GiB RAM.

**Invocation:** Ollama Python SDK with the native `tools=[]` parameter — not the OpenAI-compat endpoint. See [`src/integration/ollama_adapter.py`](src/integration/ollama_adapter.py).

**Tools defined:**

| Tool | File | What it does |
|---|---|---|
| `EXTRACT_INTAKE_FIELDS_TOOL` | [`src/integration/extraction_tools.py`](src/integration/extraction_tools.py) | Extracts `full_name`, `relationship`, `age`, `last_seen_location`, `last_seen_date`, `distinguishing_features`, `searcher_name`, `searcher_name_transliteration`, `family_members[]` |
| `ESCALATE_CRISIS_TOOL` | [`src/integration/escalate_crisis_tool.py`](src/integration/escalate_crisis_tool.py) | Triggered when `safety_rules.py` detects crisis language in any supported language; returns hardcoded IFRC/UNHCR/ICRC referral |

**Structured output:** Every tool call response is validated against a Pydantic model (`ExtractIntakeFieldsArgs`) before the result is trusted. Invalid JSON → rejection, not crash.

**Streaming:** Tool call reasoning is streamed via SSE from FastAPI to the React audit panel, making Gemma's `<|think|>` traces visible in the UI.

**Timeout:** 25s hard timeout enforced via a Clock protocol injected into the adapter. A bad audio input that produces a runaway decoder loop (observed in Phase 2.5 on low-confidence audio) is terminated, not hung.

**Anthropic-compatible endpoint:** The caseworker audit panel uses Ollama's `/v1` Anthropic-compatible endpoint — same `gemma4:e2b` model, different surface, demonstrating Ollama's multi-protocol capability.

---

## How to run

**Prerequisites:** Python 3.11+, pnpm 9+, [Ollama](https://ollama.ai), ffmpeg.

```bash
# 1. Pull the model
ollama pull gemma4:e2b

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Start backend
uvicorn ui.server.main:app --app-dir src --host 127.0.0.1 --port 8000

# 4. Start frontend (separate terminal)
cd src/ui/web
pnpm install
pnpm dev

# 5. Open
open http://127.0.0.1:5173
```

The server binds to `127.0.0.1` only — never `0.0.0.0`.

---

## Tests

**176 Python tests · 135 Vitest tests · ~311 total**

Zero real API calls in the test suite. `conftest.py` monkeypatches `socket.socket` to raise on any network attempt.

```bash
# Fast tier — core + integration, no model required (~10s)
.venv/bin/python -m pytest tests/core tests/integration -q

# Full suite
.venv/bin/python -m pytest -q

# React component tests
cd src/ui/web && pnpm vitest --run

# Type check
cd src/ui/web && pnpm exec tsc --noEmit
```

Coverage: core logic (safety rules, matching, schema validation), adapter error branches and timeout paths, FastAPI routes + SSE event types, React state transitions and component rendering. Layer boundaries enforced by AST scanner in [`tests/test_layer_boundaries.py`](tests/test_layer_boundaries.py).

---

## Architecture

Three layers. Hard boundary: no I/O in Core, no business logic above Integration.

```
┌───────────────────────────────────────────────────┐
│  UI LAYER  src/ui/                                │
│  FastAPI (127.0.0.1:8000) · React SPA · SSE       │
│  Orchestration only. Zero business logic.         │
└──────────────────────┬────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────┐
│  INTEGRATION LAYER  src/integration/              │
│  ollama_adapter      Gemma 4 E2B, 25s timeout     │
│  whisper_adapter     faster-whisper medium CPU    │
│  storage_adapter     local JSONL queue            │
│  transcription_pipeline  orchestrates both        │
└──────────────────────┬────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────┐
│  CORE LAYER  src/core/                            │
│  safety_rules    crisis detection, 6 languages    │
│  matching        phonetic-gated record matching   │
│  rfl_schema      Pydantic RFL output shape        │
│  scoring         confidence scoring               │
│  clock           Clock protocol for DI + testing  │
│  Zero I/O. Zero network. Fully testable alone.    │
└───────────────────────────────────────────────────┘
```

**Data flow:** webm blob → ffmpeg head-silence pad → Whisper ASR → `safety_rules.classify()` → Gemma `EXTRACT_INTAKE_FIELDS_TOOL` → Pydantic validation → phonetic matcher → JSONL storage → SSE stream → React.

---

## Project structure

```
kin/
├── src/
│   ├── core/                    # pure logic — no I/O
│   │   ├── safety_rules.py      # crisis detection across 6 languages
│   │   ├── matching.py          # Jaro-Winkler + corroborating-field scorer
│   │   ├── rfl_schema.py        # RFLRecord Pydantic schema
│   │   ├── scoring.py           # confidence scoring
│   │   ├── language_matrix.py   # supported language registry
│   │   └── clock.py             # Clock protocol for DI
│   ├── integration/             # adapters — zero decisions
│   │   ├── ollama_adapter.py    # Gemma 4 E2B, native tools=[], 25s timeout
│   │   ├── whisper_adapter.py   # faster-whisper medium, CPU
│   │   ├── transcription_pipeline.py  # Whisper → Gemma orchestrator
│   │   ├── extraction_tools.py  # EXTRACT_INTAKE_FIELDS_TOOL schema
│   │   ├── escalate_crisis_tool.py    # ESCALATE_CRISIS_TOOL schema
│   │   └── storage_adapter.py   # local JSONL queue
│   └── ui/
│       ├── server/              # FastAPI + SSE, 127.0.0.1 only
│       └── web/                 # React + Tailwind + shadcn/ui SPA
├── tests/
│   ├── core/                    # pure-logic unit tests
│   ├── integration/             # adapter tests against stub clients
│   ├── ui/server/               # FastAPI route + SSE tests
│   └── fakes/                   # FakeClock, FakeWhisperModel
├── results/                     # eval outputs (see below)
├── docs/                        # architecture diagram, ADRs, test strategy
└── scripts/                     # probe scripts, eval runners
```

---

## Key files

| File | What it does |
|---|---|
| [`src/integration/transcription_pipeline.py`](src/integration/transcription_pipeline.py) | Top-level orchestrator: Whisper ASR → translation → Gemma extraction |
| [`src/integration/ollama_adapter.py`](src/integration/ollama_adapter.py) | Canonical Gemma 4 E2B adapter; model tag, 25s Clock timeout, retry logic |
| [`src/integration/extraction_tools.py`](src/integration/extraction_tools.py) | `EXTRACT_INTAKE_FIELDS_TOOL` JSON schema + `ExtractIntakeFieldsArgs` Pydantic DTO |
| [`src/integration/escalate_crisis_tool.py`](src/integration/escalate_crisis_tool.py) | `ESCALATE_CRISIS_TOOL` definition |
| [`src/core/safety_rules.py`](src/core/safety_rules.py) | Crisis-phrase classifier across EN/ES/AR/FA/FR/UK — runs before Gemma |
| [`src/core/matching.py`](src/core/matching.py) | Phonetic-gated matcher: Soundex gate → Jaro-Winkler ≥ 0.85 + corroborating fields |
| [`src/core/rfl_schema.py`](src/core/rfl_schema.py) | RFLRecord, FamilyMember, Name, Age — Pydantic v2 output shape |
| [`src/integration/storage_adapter.py`](src/integration/storage_adapter.py) | Local JSONL queue; IntakeRecord + MatchLink + AuditEvent persistence |
| [`src/ui/server/main.py`](src/ui/server/main.py) | FastAPI app; lifespan warmup; 127.0.0.1:8000 bind |
| [`src/ui/web/src/App.tsx`](src/ui/web/src/App.tsx) | React SPA root; SSE consumer; state reducer wiring |
| [`tests/test_layer_boundaries.py`](tests/test_layer_boundaries.py) | AST scanner that fails the suite if Core imports I/O |

---

## Evaluation portfolio

All raw results in [`results/`](results/).

| File | What it tested |
|---|---|
| [`results/phase_2_5_final/`](results/phase_2_5_final/) | 32 probes across 9 candidate languages; confirmed EN/ES/AR/FA for full E2E |
| [`results/gemma_extraction_multilang_sweep_2026-04-29.md`](results/gemma_extraction_multilang_sweep_2026-04-29.md) | 15 Gemma tool-call runs (EN/AR/FA, 5 each) — 15/15 schema-conformant |
| [`results/whisper_baseline_20260426_114250.md`](results/whisper_baseline_20260426_114250.md) | Whisper vs. Gemma audio path; pivot evidence for two-model pipeline |
| [`results/multilang_probe_20260426_053710.md`](results/multilang_probe_20260426_053710.md) | Multilingual tool-call coherence probes |
| [`results/baseline_day4_s4_20260424_141144.json`](results/baseline_day4_s4_20260424_141144.json) | Full pipeline E2E at 4.5s warm; all 8 audit event types confirmed |
| [`results/farsi_retest_summary_20260423_084616.md`](results/farsi_retest_summary_20260423_084616.md) | Farsi confirmation after Phase 2.5 flag |

---

## Honest gaps

- No extraction-accuracy metric against labeled ground truth.
- Red-team suite designed (10 cases); execution incomplete at submission.
- French and Ukrainian have Whisper ASR coverage but no Gemma extraction sweep.
- No formal threat model. No wrong-match recovery flow. No practitioner review during build window.

---

## Links

- Demo video: [to be published]
- Kaggle writeup: [to be published]
- Contact: mark@brazinski.us
- License: MIT
