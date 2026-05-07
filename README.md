# KIN

**Offline, voice-driven intake tool for family reunification in displacement settings.**

A working prototype. Built solo in 25 days for the Google Gemma 4 Good Hackathon (Kaggle, May 2026). Not deployed. Not field-validated.

KIN takes a displaced person's voice note, transcribes it, extracts structured intake fields (names, relationships, ages, last-known locations), and checks those fields against a local registry of other records — all running on a single laptop, with no network connection required. The goal is to show that the most resource-intensive parts of a multilingual intake workflow can run offline on commodity hardware, and to surface the architectural and ethical questions that a real deployment would have to answer.

---

## Status

> **Hackathon prototype. Not deployed. Not field-validated.**
>
> This system has not been used with real cases, real displaced persons, or real caseworkers. The demo uses a fictional family (the al-Omars) performed by paid voice talent. No real biometric data, no real case files, no specific referral phone numbers appear anywhere in the codebase.
>
> Known gaps are documented below and in [`docs/`](docs/). The most significant: no formal threat model, no wrong-match recovery flow, no extraction-accuracy metric against labeled ground truth, and no conversation with practitioners during the build window (outreach sent week of submission — I'm waiting to hear back).

---

## What it does

**Voice intake, multilingual.** Whisper (faster-whisper medium, int8, CPU) handles speech-to-text across six languages. Gemma 4 E2B via Ollama handles field extraction, reasoning, and structured output. The pipeline runs locally; nothing touches the network.

**Structured extraction.** The model extracts intake fields into a multi-entity schema: one searcher record, a family roster, and a list of missing persons. Each extracted field carries provenance — the source utterance, its transcription, its translation, and what the model inferred from it.

**Cross-record matching.** A local matcher compares new records against existing ones using phonetic similarity (Soundex + SequenceMatcher), relationship-aware scoring, and configurable confidence thresholds. The matcher proposes candidate matches for caseworker review; it does not make decisions.

**Distress detection.** A semantic-embedding classifier detects crisis language across all six supported languages. When triggered, the UI surfaces a hardcoded referral to IFRC, UNHCR, and ICRC FLN by organization name — no phone numbers, because phone numbers go stale and a wrong number in a crisis referral is worse than none. The caseworker decides what to do with the referral.

**Audit trail.** Every inference produces an audit event: source utterance, Whisper transcription, English translation, extracted fields, tool call arguments, confidence score, match candidates. The trail is append-only and stored locally.

**Caseworker match review panel.** The React UI includes a panel showing match reasoning provenance — what was extracted, what the model inferred, what the confidence score was, and why. The panel is designed to support a human reviewer, not to replace one.

---

## What it is NOT

- **Not deployed.** There is no production instance. There is no hosted version. This is a local dev prototype.
- **Not field-validated.** No humanitarian practitioners reviewed this system during the build window. The workflow assumptions (intake fields, matching logic, escalation patterns) were derived from public ICRC and UNHCR documentation, not from conversations with caseworkers.
- **Not connected to existing tracing infrastructure.** KIN produces RFL-schema-compliant JSON. It does not connect to ProGres, RAIS, BIMS, the Family Links Network backend, or any real registry. The sync adapter is a stub that writes to a local queue.
- **Not a replacement for human review.** The matcher proposes candidates. A caseworker decides. This is not optional — it is the architectural commitment.
- **Not tested at scale.** The evaluation runs covered 32 probes across 9 languages during the language-selection phase, 15 tool-calling runs across 3 languages for the extraction sweep, and a handful of E2E pipeline tests. That is not a scale study.
- **Not a clinical or therapeutic tool.** Crisis detection routes to referral. KIN does not provide counseling, assessment, or follow-up.

---

## Why offline matters (and what it costs)

The architectural commitment to local-only inference is the load-bearing decision in this prototype. It means:

- **No data leaves the device.** The intake session, the extracted record, the match candidates, the audit trail — none of it touches a server. For populations with legitimate reasons to distrust data-collection infrastructure, this matters.
- **No network dependency during intake.** Connectivity in displacement settings is intermittent. A system that requires a cloud API call to complete an intake form will fail at the moments it's most needed.
- **Runs on commodity hardware.** Gemma 4 E2B (~2.3B effective parameters, ~3-5 GiB resident at Q4) fits on a 5-to-10-year-old laptop with 8-16 GiB RAM. E4B would not.

The honest cost: **local-only means no central model updates, no centralized audit, no fleet telemetry, and no one to call when the laptop breaks.** A real deployment would need to answer who maintains the local installation, how model updates get distributed, and how records sync when connectivity becomes available. This prototype does not answer those questions. It surfaces them.

---

## Quick start

You need: Python 3.11+, [Ollama](https://ollama.ai), Node.js 18+, ffmpeg.

```bash
# 1. Clone
git clone https://github.com/markbrazinski/kin.git
cd kin

# 2. Pull the model
ollama pull gemma4:e2b

# 3. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Install faster-whisper
pip install faster-whisper

# 5. React frontend (from src/ui/web/)
cd src/ui/web
pnpm install
pnpm build
cd ../../..

# 6. Start Ollama (if not already running)
ollama serve

# 7. Run the dev server
.venv/bin/python -m uvicorn src.ui.server.main:app --host 127.0.0.1 --port 8000

# Open http://127.0.0.1:8000 in a browser.
```

The server binds to `127.0.0.1` only. It does not accept connections from other machines on the network.

**Run the test suite:**

```bash
# Fast tier (core + integration, no model required)
.venv/bin/python -m pytest tests/core tests/integration -q -x

# Full suite
.venv/bin/python -m pytest -q

# React component tests (from src/ui/web/)
pnpm vitest --run
```

---

## Architecture

Three layers. No business logic above Core. No I/O below Integration.

```
┌─────────────────────────────────────────────────────────┐
│  UI LAYER  (src/ui/)                                    │
│  FastAPI server · React web app · terminal harness      │
│  Orchestration only. Zero business logic.               │
│  Server binds to 127.0.0.1. Never 0.0.0.0.             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  INTEGRATION LAYER  (src/integration/)                  │
│  ollama_adapter.py   — Gemma 4 E2B via Ollama SDK,      │
│                        25s hard timeout, Clock-injected  │
│  whisper_adapter.py  — faster-whisper medium, CPU       │
│  storage_adapter.py  — local JSON queue, no network     │
│  sync_adapter.py     — RFL-schema JSON stub (no real    │
│                        FLN backend wired up)             │
│  Adapters make zero business decisions.                  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  CORE LAYER  (src/core/)                                │
│  rfl_schema.py       — RFL fields + Pydantic validators │
│  matching.py         — phonetic-gated record matching   │
│  safety_rules.py     — crisis detection + escalation    │
│  scoring.py          — confidence scoring               │
│  language_matrix.py  — supported language registry      │
│  clock.py            — Clock protocol for DI + testing  │
│  Zero I/O. Zero network. Fully testable standalone.     │
└─────────────────────────────────────────────────────────┘
```

Voice in → Whisper transcription → English translation → Gemma 4 E2B extraction (native function calling via Ollama `tools=[]`) → Pydantic schema validation → local matcher → caseworker review panel.

The caseworker review beat in the demo uses Claude Code pointed at Ollama's Anthropic-compatible API (`http://localhost:11434/v1`). That is a separate process; KIN's own UI never opens a remote connection.

Layer boundaries are enforced by an AST scanner: [`tests/test_layer_boundaries.py`](tests/test_layer_boundaries.py).

---

## Evaluation and validation

All raw results are in [`results/`](results/). Headlines:

**Language reliability sweep — Phase 2.5** ([`results/phase_2_5_final/`](results/phase_2_5_final/)): 32 probes across 9 candidate languages. Four confirmed for full E2E demo coverage: English, Spanish, Arabic, Farsi. Five ruled out: French, Portuguese, Bengali, Ukrainian, Swahili. Tigrinya and Amharic were not evaluated. French and Ukrainian were subsequently confirmed for the Whisper-only path (transcription baseline) but are not covered by the Gemma extraction path.

**Whisper baseline** ([`results/whisper_baseline_20260426_114250.md`](results/whisper_baseline_20260426_114250.md)): faster-whisper medium vs. Gemma 4 E2B audio path on 5 shared fixtures. Whisper: 5/5 correct. Gemma audio path: 0/5 (system prompt leakage on English, dropped words on Spanish, fabricated grammar on Arabic). This is the experiment that triggered the two-model pipeline pivot: Whisper for ASR, Gemma for extraction.

**Multilingual tool-calling sweep** ([`results/gemma_extraction_multilang_sweep_2026-04-29.md`](results/gemma_extraction_multilang_sweep_2026-04-29.md)): 15 runs across English, Arabic, and Farsi (5 per language). 15/15 PASS. Schema-conformant on every run. Bytes-identical across repeated runs at temperature=0.1. Age correctly extracted as integer from Arabic and Farsi inputs with no transliteration drift.

**E2E pipeline smoke gate** ([`results/baseline_day4_s4_20260424_141144.json`](results/baseline_day4_s4_20260424_141144.json)): full pipeline at 4.5s warm. All 8 audit event types fired.

**Distress classifier probe** ([`results/gemma_extraction_multilang_sweep_2026-04-29.md`](results/gemma_extraction_multilang_sweep_2026-04-29.md)): semantic embedding confirmed for the demonstrated distress phrase. Multi-language crisis keyword list compiled and tested across EN/ES/AR/FA.

**Red-team suite**: 10 cases designed (prompt injection, fabricated fields, crisis bypass attempts, wrong-match recovery, unaccompanied minor routing, Pydantic rejection paths). Execution incomplete at submission. This is the highest-priority post-hackathon work.

**What is not in the eval portfolio:** No extraction-accuracy metric against labeled ground truth. No WER/CER measurement on real intake speech. No adversarial throughput test. No wrong-match recovery measurement.

---

## Demo

- Devpost submission: [link when published]
- Demo video: [link when published]
- Demo uses a fictional family (the al-Omars: Yusuf, Mariam, Mohamad, Aisha). Audio performed by paid Fiverr voice talent in Arabic and English. No real case data.

---

## Acknowledgments and reading

The humanitarian data protection literature is where a lot of the hardest questions in this space get worked through. The following shaped how I thought about the architectural commitments here:

- Privacy International's work on data and displacement: [privacyinternational.org](https://privacyinternational.org/topics/refugees-and-displacement)
- Sean Martin McDonald's writing on humanitarian technology and data responsibility (multiple essays via ICRC and his own publication — "Ebola: A Big Data Disaster" is the clearest statement of the failure modes this prototype is trying not to replicate)
- The Centre for Humanitarian Data's guidance on data responsibility in the humanitarian context: [centre.humdata.org](https://centre.humdata.org)
- ICRC's Handbook on Data Protection in Humanitarian Action (2020 edition)

I read these during the build window. I am not claiming expertise in the field — I am claiming that I tried to understand what I was building before I built it.

---

## Open questions

These are the questions I don't know how to answer, and the ones I'd most want to discuss with someone who works in this space:

**Language coverage.** The six languages in this prototype are the six Whisper handles reliably on CPU, not the six most-needed for displacement work. Rohingya has no viable offline ASR path I found. Tigrinya has limited training data in open models. Pidgin English variants weren't evaluated. How do you make an intake tool useful for the populations who need it most when the models weren't trained on their languages?

**Scale and throughput.** This prototype runs one intake at a time on a laptop. What does the architecture look like at a registration site processing 300 people per day? What's the right hardware target for that setting?

**Threat model.** I did not formally document adversarial use cases: traffickers, hostile state actors, bad-faith family members claiming to search for someone, partner-organization data handoff without consent. A real deployment needs this analysis done before anything goes live.

**Wrong-match recovery.** The UI surfaces match candidates. The caseworker rejects them. What happens to the rejected match — is it logged, is it flagged, does it affect the confidence threshold for future matches? This flow is designed but not implemented.

**Maintenance.** I built this in 25 days for a hackathon. Who maintains it after the hackathon? How do model updates get distributed to offline installations? How do records sync when connectivity becomes available? I don't have answers.

If you work in humanitarian data, field registration, or displacement response and want to tell me where the assumptions here are wrong — I want to hear from you.

---

## Contact

Mark Brazinski — mark@brazinski.us

---

## License

[MIT](LICENSE)

This software is provided as-is. It is a prototype. It has not been validated for use in real humanitarian operations. Do not deploy it without independent review by people who understand the operational context.
