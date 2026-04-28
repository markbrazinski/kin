# KIN — Master Project Plan

> Living document. Commit to repo root. Update at every checkpoint and
> major decision. If this file and reality diverge, reality wins and
> this file gets updated same-day.

Last updated: May 1, 2026 — Phase 1 certified. The runtime spine that
Day 11 prereq verification surfaced as missing landed clean across six
sessions Apr 27 – May 1. Six commits (`9615bcd` → `bfa50e9`); test
count 75 → 119; smoke gate green against real Whisper + real Gemma
(4.5s pipeline / 7.82s test wall-clock warm). All eight audit_event
types from Part 1 REV 4 enum have ≥1 test asserting emission. Layer
boundary green throughout; zero regressions across the 113 pre-existing
tests.

`ingest_audio(audio_path, lang, source_device_id, *, whisper, ollama,
storage)` is the live pipeline entry point. End-to-end: audio file →
Whisper transcription → Gemma translation (skipped if EN) → safety_rules
classification → Gemma tool_call extraction → IntakeRecord persisted →
matching trigger fires → audit trail written. Crisis records skip
extraction + matching; field-level audit events emit per Part 1 REV 4
mapping; ADR-004 records the orchestration architecture rationale.

Frontend still on setTimeout fakes. Bundle 1 (May 2-4) replaces the
setTimeout sequencer with real SSE wiring + builds the four high-risk
UI affordances flagged in Part 2 REV 3: merge animation, two-device
differentiation, structlog sidebar, JSON function-call sidebar.

Maintainer: Mark Brazinski (solo developer)
Next scheduled update: end of Bundle 1 (~May 4) or at first material
decision change.

---

## 1. What we're building and why

**KIN** is an offline, multilingual family-reunification intake copilot
built for aid workers in low-connectivity field settings. It runs on a
laptop (MacBook Air M4, 16 GiB RAM) with no external network
dependency. It accepts voice intake in English, Spanish, Arabic, or
Farsi, produces structured records compatible with Primero and proGres
data shapes, and surfaces cross-session matches when the same missing
person appears in two aid workers' records under different
transliterations. KIN's transcription stage uses Whisper (OpenAI's
open-source multilingual ASR model, run locally) for audio-to-text;
Gemma 4 E2B handles all downstream reasoning — structured intake
record building via native tool-calling, multilingual safety
classification, text-only translation, and caseworker review. Both
models run offline on the laptop, no network dependency.

### The real problem

The International Committee of the Red Cross (ICRC) reunification
program reports a **4.1% success rate** on family-reunification
requests (309 of 7,490 in published data). The bottleneck is not
intent or funding — it's data fragmentation. When two aid workers in
different tents interview separated family members about the same
missing child, the records never converge because the names are
transliterated differently and the systems don't speak to each other.
117.3 million people are currently displaced globally; 49 million of
them are children.

### Framing (locked)

"An aid-worker copilot for family-reunification intake, designed to
feed Primero/proGres-shaped records."

Narrator voice in demo video: Principal PM at Twilio.
Hero of the story: displaced parent.
Primary customer persona: field aid worker.
Primary beneficiary: separated family member (usually a child).
Demo moment at 1:30 of the final video: "One child. Found."

### What KIN is not

KIN is not an independent humanitarian platform, not a Primero
replacement, not a consumer app, not a matching algorithm competing
with ICRC's systems. It is a copilot that produces structured records
the existing systems can ingest, and surfaces matches the existing
systems would miss because of transliteration variance.

---

## 2. The hackathon

**Gemma 4 Good Hackathon** (Kaggle)
Deadline: May 18, 2026, 23:59 UTC
Target submission: May 17, 2026 (1-day buffer)
Primary prize target: Digital Equity & Inclusivity ($10,000)
Secondary prize categories entered where KIN naturally qualifies —
each gets a per-category "why this wins" paragraph at zero marginal
cost.

Judges: Kaggle-platform judges + Google DeepMind representatives +
humanitarian-sector SMEs (lineup published on Kaggle rules page).
Judges review online only — they never run the code. The demo video
and the Kaggle writeup are the deliverables.

Submission format: Kaggle notebook + repo link + demo video (YouTube
unlisted) + writeup.

---

## 3. Architecture (locked)

Three-layer hexagonal design. Enforcement is non-negotiable — a CI test
validates layer boundaries via AST import scanning (in place since Day 3
scaffolding, green throughout Phase 1).

```
┌──────────────────────────────────────────────────┐
│  UI layer (src/ui/)                              │
│  - FastAPI server (127.0.0.1 only, no network)   │
│  - React + Vite + TypeScript web app             │
│  - Terminal demo harness                         │
│  - May import from Core and Integration          │
│  - Never contains business logic                 │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│  Integration layer (src/integration/)            │
│  - whisper_adapter (audio → text transcription   │
│    in source language; faster-whisper backend,   │
│    whisper-medium int8, structlog, timeout)      │
│  - ollama_adapter (text → text reasoning;        │
│    translate() + tool_call() methods; canonical  │
│    25s timeout, retry-once on transient failure, │
│    think=False enforcement, structlog)           │
│  - storage_adapter (JSONL CRUD, audit-event      │
│    auto-write, single-writer)                    │
│  - sync_adapter (RFL-shaped JSON export, stub    │
│    awaiting Primero integration)                 │
│  - transcription_pipeline (orchestration:        │
│    transcribe_and_translate + ingest_audio +     │
│    _trigger_matching)                            │
│  - extraction_tools (EXTRACT_INTAKE_FIELDS_TOOL  │
│    JSON Schema + ExtractIntakeFieldsArgs)        │
│  - system_clock (Clock Protocol impl with        │
│    monotonic() + now())                          │
│  - May import from Core only                     │
│  - Never imports from UI (upward forbidden)      │
│  - Makes zero business decisions                 │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│  Core layer (src/core/)                          │
│  - storage_schemas (IntakeRecord, MatchLink,     │
│    AuditEvent — Pydantic v2 with Literal enums)  │
│  - tool_calling (ToolCallResult Pydantic model)  │
│  - rfl_schema (in-flight extraction model:       │
│    Name, Age, LastSeen, Guardian, RFLRecord)     │
│  - safety_rules (crisis detection across 4 langs │
│    via keyword matching)                         │
│  - matching (two-stage pairwise: Jaro-Winkler    │
│    ≥0.85 gate + composite ≥0.70 threshold;       │
│    no LLM in path)                               │
│  - language_matrix (supported langs, routing     │
│    helpers)                                      │
│  - clock (Clock Protocol with monotonic + now)   │
│  - Zero I/O. No network, no disk, no model       │
│    calls.                                        │
│  - Fully testable without any external           │
│    dependency                                    │
└──────────────────────────────────────────────────┘
```

### Why this architecture

Three reasons, each doing real work:

**1. Single-responsibility models.** Whisper is purpose-built for
offline multilingual ASR — trained on 680,000 hours of multilingual
audio, de-facto reference for the task. Gemma 4 E2B is purpose-built
for text reasoning under constrained compute. Each model does what
it's best at. The decision was empirically driven: Days 8-9 falsified
Gemma's audio path across 30+ test calls, three different format-
enforcement attempts, audio preprocessing variations, and sampling
parameter tuning. Whisper baseline (Day 10 morning) recovered full
utterances correctly across all four KIN languages where Gemma
either dropped content or confabulated.

**2. Testability.** Core is pure — unit tests run in milliseconds with
no fixtures, no network mocks, no model calls. Integration tests use
stub clients at each adapter seam. UI is dumb and orchestrated through
Core. The two-adapter Integration layer means whisper-side and
gemma-side failures are isolated and independently testable. Phase 1
shipped 119 tests with zero real API calls outside the single opt-in
smoke test.

**3. Demo reliability.** If Whisper hangs (it shouldn't — local model,
deterministic latency ~8s for whisper-medium), 25s timeout pattern
inherited from ollama_adapter contains the damage. If Gemma hangs on
text-only reasoning, same protection. A demo machine never hangs on
stage. Phase 1 smoke test verified 4.5s warm pipeline against real
models — comfortable headroom under any timeout budget.

**4. Defensibility against "it's just a Gemma wrapper."** Judges who
ask "what did you build besides call Gemma?" can point to: (1) the
two-model architectural decision with empirical evidence (ADR), (2)
the Core layer's safety rules, matching logic, scoring, invariants,
and (3) the Integration layer's adapter discipline (retry-once,
timeout-bounded, audit-logged, layer-enforced). Multi-model pipelines
are how production AI systems are built. KIN demonstrates engineering
judgment, not just model usage.

### Key technical locks

- **Matching:** source-script exact + transliteration fuzzy via
  cross-script Jaro-Winkler (≥0.85 gate) + corroborating fields scored
  against 0.70 composite threshold. Two-stage: phonetic match is a
  gate, corroborating fields are validators. Pure-Core, no LLM in
  matching path. Empirically validated Day 10 — locked thresholds held
  on first run against 7 test fixtures. Same-script exact + ≥1
  corroborating → high confidence (loosened from spec's ≥2 because
  exact same-script match is the strongest possible name evidence;
  documented in `docs/matching.md` §5). Human-in-the-loop confirmation,
  no auto-merge. Runtime trigger entry point `_trigger_matching` lives
  in `transcription_pipeline.py` per ADR-004; `docs/matching.md` §9
  documents the contract.
- **ASR model:** **Whisper-medium int8** via faster-whisper (CTranslate2
  backend). NOT whisper-tiny/base/small (multilingual accuracy on
  AR/FA insufficient). NOT whisper-large-v3 (latency exceeds budget
  on 16GB MacBook Air). Empirically validated on all four KIN
  languages Day 10 morning at ~8s per inference; smoke test validated
  Spanish at 3.84s (warm) May 1.
- **Reasoning model:** **Gemma 4 E2B** at `think=False` (NOT E4B, NOT
  26B, NOT 31B). E2B runs comfortably on 8-16 GB field hardware.
  Used for text-input reasoning: structured intake (via native
  tool-calling), translation, safety classification, caseworker review.
  ADR-003 records the `think=False` decision; enforced at exactly one
  SDK call site (`_call_with_timeout`) per S3 verification.
- **Extraction surface:** Gemma 4 E2B's **native tool-calling API** via
  `OllamaAdapter.tool_call()`. Apr 28 hello-world cleared GREEN on
  Spanish; Apr 29 multilang sweep cleared GREEN across EN/AR/FA (15/15
  PASS, native script preserved). Bytes-identical output across runs.
  ADR-004 records the alternatives rejected (`format=<schema>` silently
  dropped under `think=False`; regex/grammar parsing brittle on
  multilang).
- **Languages:** **EN / ES / AR / FA** in active demo path. **FR / UK**
  added to `SupportedLanguage` enum (six total) for storage-layer
  capacity. Whisper-medium handles all four demo languages cleanly;
  Phase 2.5's nine evaluations and rule-outs (Swahili, Bengali,
  Amharic, etc.) remain valid.
- **Pipeline:** audio → Whisper transcribe (source language) → Gemma
  text-only translation (English; skipped if `lang="en"`) →
  safety_rules.classify (source text) → Gemma tool_call extraction
  (source text) → IntakeRecord persistence + audit trail → matching
  trigger. Crisis path branches early: skip extraction, skip matching,
  persist as `paused_for_crisis` with referral fields. Latency budget:
  ~8s Whisper + ~2s Gemma translate + ~1s Gemma tool_call ≈ ~11s
  cold, 4.5s warm. Comfortably under 25s timeout per stage.
- **Audio:** ffmpeg head-silence padding required before Whisper
  inference; `whisper_adapter` owns this (lifted from `ollama_adapter`
  pattern).
- **Timeouts:** 25 seconds per inference call across both adapters,
  enforced via FakeClock-driven tests. Single timeout-race code path
  shared between `translate()` and `tool_call()` (S3 widening of
  `_call_with_timeout`).
- **Storage:** `storage/` directory at repo root, gitignored. Three
  JSONL files: `intake_records.jsonl`, `match_links.jsonl`,
  `audit_events.jsonl`. Single-writer assumption documented in
  `storage_adapter.py`. Read-modify-write for updates. UUID + tz-aware
  UTC timestamps via Clock-injected `now()`.

---

## 4. The 17-Day Calendar Plan (Apr 27 – May 17, 2026)

### Phase 1: Orchestration Build (Apr 27 – May 1, 5 calendar days, 6 sessions) — ✅ CERTIFIED

- Apr 27: Re-plan complete. Async tracks queued: Spanish recording,
  Fiverr orders placement, caseworker outreach. Architecture diagram
  shipped. Demo agent thread produced Part 1 REV 4 + Part 2 REV 3 +
  Part 3 Fiverr review.
- Apr 28: Hello-world Gemma extraction test — 5/5 PASS Spanish,
  GREEN verdict. Tool-calling API path unblocked over structured-
  output approach.
- Apr 29: S1 multilang sweep (15/15 PASS EN/AR/FA, GREEN). S2 storage
  layer (97 tests). S3 extraction tool-calling (107 tests). S4
  ingest_audio orchestration (113 tests).
- Apr 30: S5 matching trigger + audit verification + ADR-004 (118
  tests). All 8 audit_event types covered.
- May 1: S6 smoke test infrastructure + TTS fixture re-point.
  Phase 1 smoke gate GREEN against real Whisper + real Gemma.
  Phase 1 CERTIFIED.

Commit chain:
```
bfa50e9 phase-S6 followup: TTS fixture re-point + smoke GREEN
2a48878 phase-S6: Phase 1 smoke test infrastructure
eeafcc4 phase-S5: matching trigger + ADR-004 + matching docs §9
c97f86e phase-S4: ingest_audio orchestration
cd82c3a phase-S3: ollama tool_call() + extract_intake_fields tool
9615bcd phase-S2: storage layer (IntakeRecord/MatchLink/AuditEvent + Clock.now())
```

### Phase 2 / Bundle 1: SSE + UI Affordances (May 2-4, 3 days, ~6 sessions) — NEXT

Brief lives at `briefs/bundle-1-context.md` (or wherever Mark places
it). Six provisional sessions, refined at planning gate:

- S1: SSE backend (FastAPI streaming endpoint, tail-following file
  watcher, audit_events.jsonl + structlog stream)
- S2: SSE frontend consumer (React EventSource hook, replaces
  setTimeout fakes)
- S3: Affordance (b) two-device differentiation (themed split-view,
  per-panel SSE filter by `source_device_id`)
- S4: Affordance (b.1) transliteration entry + (c) structlog sidebar
  wiring (per audit-event-to-UI mapping table from Part 2 REV 3)
- S5: Affordance (d) JSON function-call sidebar (real Gemma
  tool_call output rendered via syntax-highlighted JSON)
- S6: Affordance (a) merge animation + integration smoke (browser →
  SSE → backend → ingest_audio → audit stream → UI render)

After Bundle 1: Beats 4, 5, 6, 7, 8 all demo-ready except pre-seeded
data (Bundle 2 territory).

### Phase 3 / Bundle 2: Tent A snapshot + smoke (May 5-6, 2 days, ~3-4 sessions)

- May 5: Fiverr audio expected delivery window starts. Tent A
  Mohammed snapshot mechanism (real-pipeline-ingest first time,
  snapshot-and-restore after). Pre-seed baseline records (6 records
  + 1 confirmed match link per Part 1 REV 4).
- May 6: End-to-end smoke test on demo audio with full UI rendering.
  LLM-as-judge Pass 1 — orchestration verdict.
- Boss-mode checkpoint: are we recording May 7-9 or do we slip?

### Phase 4: Safety-Net Video Window (May 7-9, 3 days)

- May 7: First safety-net recording attempt. Lighting, mic,
  screen-capture pre-flight. Multiple takes per beat.
- May 8: Re-record window if May 7 surfaced issues.
- May 9: Tag `safety-net-v1`. You can submit today if needed.
  Non-negotiable milestone.

### Phase 5: ⛔ FEATURE FREEZE — May 10

No new features after this date. Only fixes, polish, content.

### Phase 6: Polish + LLM-as-Judge Passes (May 10-12, 3 days, ~4-5 sessions)

- May 10: README polish, ADR writes, threat model section.
  Devpost framing rewrite.
- May 11: LLM-as-judge Pass 2 — full submission verdict. Apply
  highest-impact fixes.
- May 12: Demo artifacts live and clickable. Final end-to-end
  run on clean data.

### Phase 7: Final Video Production (May 13-15, 3 days)

- May 13: VO script lock. Demo coach review on script.
  First take of demo video.
- May 14: Recording takes 2 and 3. Edit begins.
- May 15: Final edit. Upload unlisted. LLM-as-judge Pass 3 —
  video-as-artifact verdict.

### Phase 8: Submission (May 16-17)

- May 16: Submit. Verify all links and artifacts.
- May 17: Deadline. Touch nothing.

### Async tracks (parallel to all phases)

- **Caseworker outreach:** ongoing through Phases 1-3, hope for
  testimonial by Phase 5 cutoff (May 6 deadline to incorporate into
  final video)
- **Fiverr orders:** ready to release post-May-1 (Spanish gigs 1, 2A;
  Arabic gigs 2B, 3; skip Order 4 Farsi). Expected delivery May 5-7.
- **Spanish self-recording:** 15 min, anytime, optional pre-Bundle-1
  for non-TTS audio in `audio_samples/`
- **Competitive scan round 2:** May 11-12 alongside polish

### Risk lines

- Bundle 1 not solid by May 6 → Boss-mode, possibly slip safety-net
  to May 9-10, push freeze to May 11.
- Final video reveals problems May 15 → emergency re-cut May 16,
  zero buffer.
- Fiverr audio late or unusable → fall back to TTS Spanish + Mark
  self-recording for May 7-9 safety-net video.

---

## 5. Why each area gets investment

Investment allocation follows the "judges watch the video, not the
code" principle. Percentages are approximate effort, not hours.

| Area | Effort % | Why |
|---|---|---|
| Planning + architecture | 10% | Foundation; wrong architecture makes everything else harder |
| UI migration + scaffolding | 15% | The demo happens in this UI; it must be real, not mocked |
| Gemma + Whisper integration | 20% | Core technical risk; failure here kills demo |
| Core logic (safety, matching, schemas) | 20% | Defensibility; the "what did you build besides call Gemma" answer |
| Testing (~120 meaningful tests) | 10% | Reliability for the demo; also signals engineering rigor |
| Devpost writeup + evidence | 10% | First filter judges see; must be done well |
| Demo video production | 15% | The artifact judges actually score; 10 min raw → 2:20 final |

### What doesn't get investment

- A general-purpose chat UI. KIN is intake, not conversation.
- More than 4 demo languages. EN / ES / AR / FA are the demo set
  (FR / UK are storage-layer-supported but not demo-features).
- Cloud storage, sync, or multi-device. Offline-first, laptop-only.
- Fine-tuning Gemma. Out-of-the-box E2B is sufficient.
- Real photo intake. Placeholder in UI; feature stubbed.
- OCR, handwriting, barcode. Voice intake only.
- Production-grade auth / multi-user / audit logs beyond structlog.
  Single field laptop; multi-user is out of scope.
- Real ICRC / REFUNITE API integration. Sync adapter is a stub.
- Concurrent storage writes. Single-writer assumption documented.

If an idea surfaces during build that doesn't fit these constraints,
the answer is no — regardless of how good the idea is — unless it's
both load-bearing for the demo AND achievable in < 4 hours.

---

## 6. Area charters

Each charter is self-contained. A new agent can read any one charter
and know what that area is, what it produces, what "done" looks like,
what's already decided, and what to watch for.

### 6.1 Planning + architecture

**Goal:** Reliably run Whisper-medium for offline multilingual ASR
and Gemma 4 E2B for text-only reasoning, producing structured intake
records on a 16GB MacBook Air. Each model does what it's best at;
neither is asked to do work outside its strength.

**Status:** ✅ Done. `whisper_adapter` + `ollama_adapter` +
`transcription_pipeline.ingest_audio()` shipped. End-to-end smoke
test verified May 1 (4.5s warm).

**Definition of done — all met:**
- Hello-world: 5 seconds of audio → transcription + translation +
  parsed RFL fields — works in all 4 demo languages ✅
- 5/5 PASS on Apr 28 Spanish hello-world ✅
- 15/15 PASS on Apr 29 multilang sweep (EN/AR/FA) ✅
- Timeout test fires reliably for both adapters (FakeClock-driven) ✅
- Structured output validates 100% of the time (native tool-calling) ✅
- No runaway loops in red-team suite ✅
- Layer boundary test green throughout (8/8) ✅

### 6.2 UI migration + scaffolding

**Goal:** Production-grade, TypeScript-typed, strict-mode React app
serving as the substrate for the demo video, hosting the real SSE
stream from the Python backend.

**Status:** Days 1-7 React work stable. SSE wiring is Bundle 1.

**Bundle 1 deliverables:**
- Real SSE client replacing setTimeout demo sequencer
- Two-device differentiation (themed split-view)
- Transliteration entry affordance in IntakePanel
- Structlog sidebar wired to real event stream
- JSON function-call sidebar with syntax-highlighted Gemma tool-call
  output
- Merge animation (CSS keyframes, polish)

**Definition of done (Bundle 1):**
- All four affordances render correctly against real audit-event
  stream
- Whole-tree `tsc --noEmit` green
- Two-device differentiation passes the "two tents, not two columns"
  read test
- Structlog sidebar matches what's actually happening (no stale
  setTimeout fakes)
- JSON function-call sidebar shows real Gemma tool-call output, not
  hardcoded JSON

### 6.3 Gemma + Whisper integration

**Goal:** Reliably run Whisper-medium and Gemma 4 E2B across four
languages, producing structured intake records via native tool-calling
without hanging, crashing, or looping.

**Status:** ✅ Done. Both adapters live, both tested, both running
under 25s timeout enforcement.

**Key historical milestones:**
- Day 4 Session 4: Gemma `think=False` discovery (commit `6a45326`)
- Day 5 Sessions 1A/1B: OllamaAdapter skeleton + behavior layer
  (`e1baa9d`, `e3093bc`)
- Day 6 Session 2: GGML retry mechanism (`5306d1d`)
- Day 7 Sessions 1-2: multilingual routing (EN/ES/AR/FA via
  `language_matrix`)
- Days 8-9: structured-output saga falsified format=<schema> path
- Day 10: Whisper baseline experiment + two-model pipeline pivot
- Day 10 commits `76f3d24` / `31ee5d8` / `4c4785b`: pipeline +
  multilingual safety + matching
- Apr 28: hello-world Spanish tool-calling GREEN
- Apr 29 (S1): multilang sweep EN/AR/FA GREEN
- Apr 29 (S3): `OllamaAdapter.tool_call()` shipped (commit `cd82c3a`)
- May 1 (S6): smoke gate green against real models

### 6.4 Core logic (safety, matching, schemas)

**Goal:** Provide the defensibility layer that separates KIN from a
Gemma chat wrapper — the logic that runs before, around, and after
every model call, enforcing invariants the model alone can't.

**Status:** ✅ Feature-complete.

**Modules:**
- `rfl_schema.py` — in-flight extraction model (Day 6 Session 3)
- `safety_rules.py` — keyword crisis detection across 4 langs (Day 10)
- `matching.py` — pure-Core two-stage pairwise (Day 10, locked)
- `language_matrix.py` — supported langs, routing helpers (Day 7)
- `clock.py` — Clock Protocol with `monotonic()` + `now()` (Day 3 + S2)
- `storage_schemas.py` — IntakeRecord, MatchLink, AuditEvent (S2)
- `tool_calling.py` — ToolCallResult Pydantic (S3)

**Key decisions locked in code + docs:**
- Matching threshold: 0.70 composite, 0.85 Jaro-Winkler gate
- No LLM in matching path (architectural)
- Same-script exact + ≥1 corroborating → high (loosened from spec ≥2)
- Pydantic v2, Literal types for enums (matches existing convention)
- Source script preserved alongside transliterations — never normalized
- Crisis detection blocks extraction + matching (orchestration-layer
  branching per ADR-004)

### 6.5 Testing

**Goal:** Test suite that demonstrates reliability to judges, catches
regressions during development, proves the core invariants hold.

**Status:** ✅ 119 tests defined (was 75 pre-Phase-1).

**Test count progression:**

| Phase | Count | Delta |
|---|---|---|
| Pre-S2 baseline | 75 | — |
| Post-S2 (storage layer) | 97 | +22 (20 storage + 9 Clock) |
| Post-S3 (extraction tool-calling) | 107 | +10 |
| Post-S4 (orchestration) | 113 | +6 |
| Post-S5 (matching trigger + audit) | 118 | +5 |
| Post-S6 (Phase 1 smoke) | 119 | +1 (smoke) |

**Run modes:**
- `pytest` → 118 fast tests in ~8s (smoke excluded by default via
  `addopts = "-m 'not smoke'"`)
- `pytest -m smoke` → 1 real-models smoke test in ~14s cold / ~8s warm

**Coverage discipline:**
- Zero real API calls in fast tests; all external I/O mocked
- Smoke test is the only test that hits real Whisper + real Gemma
- Layer boundary test green (8/8 throughout)
- All 8 audit_event types from Part 1 REV 4 enum have ≥1 test
  asserting emission
- Test budget caps per session (S2 hit 29 with Clock surplus called
  out, S3 hit 10, S4 hit 6, S5 hit 5, S6 hit 1)

### 6.6 Devpost writeup + evidence

**Goal:** Land a Kaggle writeup that earns 3 minutes of video-watching
time, with KIN's claims backed by clickable evidence.

**Status:** Pre-pivot draft exists; rewrite scheduled May 10.

**Bundle 6 (Phase 6) deliverables:**
- Kaggle submission writeup (Devpost agent drafts, Mark reviews)
- Headline statistic prominently placed
- Per-prize "why this wins" paragraphs (Digital Equity + secondary
  categories)
- Evidence bundle: architecture diagram (already shipped), test
  coverage snapshot, red-team suite results, smoke gate output
- README.md at repo root for judges who click through
- Link to demo video (unlisted YouTube)
- Link to GitHub repo (public)

### 6.7 Demo video production

**Goal:** 2:20 (±10s) demo video that lands "One child. Found." within
the first 90 seconds and survives muted mobile playback.

**Status:** Storyboard locked (v2 demo script, 9 segments). Recording
windows May 7-9 (safety-net) and May 13-15 (final).

**Deliverables (already locked or done):**
- Storyboard (locked)
- Architecture diagram (Devpost-quality, shipped Apr 27)
- Fiverr brief (Part 3, locked)
- VO script (Phase 5.7 output, May 13)

**Deliverables (pending):**
- Safety-net video recorded May 9 (non-negotiable)
- Final video recorded May 13-15, 3 takes minimum
- Edit: B-roll, captions, audio cleanup
- Upload unlisted, link from Kaggle submission

---

## 7. What's done, what's locked, what's open

### Done

**Pre-Phase-1 (Days 0-10):**

- Phase 0-5C planning (framing, architecture, test strategy, prize
  strategy)
- Phase 3 Block A + B + B.5: TypeScript conversion, primitives split,
  shared types extraction
- Day 3: Python scaffolding (uv + setuptools + ruff), Clock Protocol,
  FakeClock, layer boundary test (commits `87454cc`, `71919d9`)
- Day 4: SystemClock adapter, Ollama bridge with cancellation race,
  Gemma `think=False` discovery, ADR-002 + ADR-003 (commits `473424c`,
  `e18b595`, `6a45326`, `12b38d5`)
- Day 5: OllamaAdapter skeleton + behavior layer, structlog wiring,
  Day-1 anchor timeout test (commits `403898e`, `e1baa9d`, `e3093bc`,
  `4469119`, `0087de1`)
- Day 6: First-pass safety_rules (English), GGML retry mechanism, RFL
  schema expansion (commits `bd9e734`, `5306d1d`, `7b0470a`)
- Day 7: Language routing for ES + AR + FA, language_matrix module
  (commits `1ddf88c`, `8fa3715`)
- Days 8-9: format=<schema> falsified, audio preprocessing falsified,
  parameter-tuning approach falsified — collectively cleared the path
  to two-model pivot
- Day 10: Whisper baseline experiment, two-model pipeline shipped,
  multilingual safety_rules across all 4 demo langs, matching logic
  with confidence bands (commits `76f3d24`, `31ee5d8`, `4c4785b`)

**Phase 1 (Apr 27 – May 1):**

- **S1 multilang sweep** (Apr 29): scripts/gemma_extraction_multilang_sweep.py,
  results/gemma_extraction_multilang_sweep_2026-04-29.md. 15/15 PASS
  EN/AR/FA. Native script preserved. ADR-003 lock holds across all
  three languages. ~22 min total.
- **S2 storage layer** (commit `9615bcd`): IntakeRecord + MatchLink +
  AuditEvent Pydantic models. JSONL CRUD with audit-event auto-write.
  Clock Protocol extension (`now()` method). Single-writer assumption
  documented. 97 tests passing.
- **S3 extraction tool-calling** (commit `cd82c3a`): OllamaAdapter
  gains `tool_call()` method. EXTRACT_INTAKE_FIELDS_TOOL JSON Schema
  + ExtractIntakeFieldsArgs Pydantic. InvalidToolCall relocated to
  `_errors.py`. `_call_with_timeout` widened to share single
  timeout-race code path between translate and tool_call.
  `think=False` enforced at exactly one SDK call site. 107 tests
  passing.
- **S4 ingest_audio orchestration** (commit `c97f86e`): end-to-end
  pipeline. `_persist_crisis_record`, `_build_extraction_messages`,
  `_map_extraction_to_intake`, `_OllamaPort` Protocol. Pre-flight
  resolutions held: source-text to extraction (not English),
  propagate-on-failure, is_minor real field + structlog event,
  safety_rules input is source language, status=complete emits no
  audit event. 113 tests passing.
- **S5 matching trigger + audit verification + ADR-004** (commit
  `eeafcc4`): `_trigger_matching` fan-out wrapper, `_to_rfl_record`
  bridge, `_source_script_for_lang` helper, Stage 7 wire-in to
  ingest_audio. ADR-004 documents extraction-via-tool-calling +
  matching-trigger-placement + crisis-path branching + bulk vs
  progressive field_extracted emission. docs/matching.md §9 added.
  All 8 audit_event types covered by ≥1 test. 118 tests passing.
- **S6 Phase 1 smoke test** (commits `2a48878`, `bfa50e9`):
  test_phase1_smoke.py (single test, opt-in via `pytest -m smoke`).
  TTS Spanish fixture (`spanish_intake_tts_01.wav`) — pivot from
  original `spanish_01.wav` after fixture-content gap surfaced as a
  real smoke-test signal. Smoke test GREEN against real Whisper +
  real Gemma. 4.5s pipeline / 7.82s test wall-clock warm. **Phase 1
  CERTIFIED.**

### Locked (not revisited without explicit Boss-mode decision)

#### Architecture Decision Records

| ADR | Subject | Status |
|---|---|---|
| ADR-001 | Web UI as primary demo surface | LOCKED |
| ADR-002 | Test strategy reconciliation (asyncio_mode + import paths) | LOCKED |
| ADR-003 | Gemma `think=False` enforcement | LOCKED |
| ADR-004 | Orchestration architecture (extraction-via-tool-calling, matching-trigger placement, crisis-path branching, bulk vs progressive field_extracted emission) | LOCKED |

#### Core framing + scope

- Framing: aid-worker copilot for intake, feeds Primero/proGres
- Hero: displaced parent. Persona: field aid worker.
  Beneficiary: separated family member.
- Demo moment 1:30: "One child. Found."
- Demo video target: 2:20 (±10s)
- Submit date: May 17, 2026 (1-day buffer ahead of May 18 deadline)
- Primary prize: Digital Equity & Inclusivity ($10K)

#### Architecture + tech stack

- Hexagonal three-layer (Core / Integration / UI), AST-enforced
- Models: Whisper-medium int8 (faster-whisper) + Gemma 4 E2B at
  `think=False`
- Demo languages: EN / ES / AR / FA. Full enum: en/es/ar/fa/fr/uk.
- Adapter timeout: 25 seconds
- ASR / reasoning split: Whisper does ASR, Gemma does text reasoning
  (translate, safety, extraction via native tool-calling, caseworker
  review)
- `format=` parameter abandoned for Gemma calls (Day 8 evidence)
- Pydantic v2, Literal types for enums (no Enum subclasses)
- Python packaging: uv + setuptools + ruff, src/ layout
- Pydantic + structlog as production deps

#### Phase 1 cross-session decisions (govern any code touching the pipeline)

- **IntakeRecord shape:** flat per Part 1 REV 4 spec. No nested
  RFLRecord. `ConfigDict(extra='ignore')`.
- **RFLRecord** stays as the in-flight extraction model. Storage owns
  persistence (flat); matching owns the algorithm domain (nested).
  `_to_rfl_record(intake)` in `transcription_pipeline.py` translates
  between them.
- **Storage location:** `storage/` at repo root, gitignored. Three
  JSONL files.
- **UUID + timestamps:** `uuid4()` for IDs. Tz-aware UTC timestamps
  via Clock-injected `now()` (Protocol extension over WallClock split).
  `StorageAdapter` accepts a Clock; FakeClock for tests.
- **Concurrency model:** none. Read-modify-write for updates.
  Single-writer assumption documented in `storage_adapter.py`.
- **Audit-event mapping ownership:** lives in `storage_adapter`
  (auto-write on CRUD). Pipeline never writes audit events directly —
  triggers them via storage operations. Part 1 REV 4 audit-event
  mapping table is the contract.
- **Matching-trigger placement:** orchestration, not storage.
  `_trigger_matching` in `transcription_pipeline.py` next to
  `ingest_audio`. ADR-004 records rationale.
- **Crisis-path branching:** `safety_rules.classify(is_crisis=True)`
  → persist `paused_for_crisis` record with referral fields, return.
  No tool_call invocation, no `_trigger_matching` call.
- **Bulk vs progressive field_extracted emission:** orchestration
  emits all field_extracted events at once after a single tool_call.
  Beat 5's progressive turn-by-turn appearance is Bundle 1's concern,
  resolved via either three sequential audio files or staggered SSE
  rendering.
- **Mapping rules:**
  - Latin-script langs (en/es/fr): `full_name_source_script` =
    `full_name_transliteration` = `args.full_name`
  - Non-Latin langs (ar/fa/uk): `full_name_source_script = args.full_name`,
    `full_name_transliteration = ""` (worker-entered)
  - `is_minor = (args.age is not None and args.age < 18)`
  - `crisis_match_path = "keyword"` if matched_keywords non-empty,
    else None. (`"semantic"` defined but unwritten until future work.)
  - `minor_flagged` event is structlog-only, NOT persisted as
    audit_event (Part 1 REV 4 enum constraint).

#### Adapter and Core library locks

- Gemma 4 E2B `think=False` at exactly one SDK call site
  (`_call_with_timeout`). ADR-003 records.
- structlog `25.5.0` in prod deps. Adapter event payload schema
  per `test_strategy.md §2`.
- Adapter exception count: 7 classes. `AdapterError` base + 6
  concrete (`PaddingUnavailable`, `PaddingFailed`,
  `InferenceTimeout`, `InvalidToolCall`, `InferenceFailed`,
  `UnsupportedLanguage`). InvalidToolCall lives in `_errors.py`.
- Ollama daemon 0.21.0 confirmed working. Python SDK `ollama==0.6.1`
  is a distinct semver track.
- `asyncio.to_thread` cancellation: Core-time guarantee only.
  Adapter's 25s timeout bounds Core latency, not daemon computation.
- GGML retry catch-tuple: `(ollama.ResponseError,
  ollama.RequestError)`. Retry once, surface as `InferenceFailed`.
  `InferenceTimeout` propagates without retry.
- `safety_rules.SafetyResult` schema: `is_crisis` +
  `matched_keywords` + `suggested_action` (Literal block_intake/proceed)
  + `crisis_resources_locale`.
- RFL schema versioning: single growing `RFLRecord`. Hackathon scope.
- `RFLRecord` shape: `Name { canonical, source_script, transliterations }`,
  `Age { value, confidence }`, `Guardian { present, consent }` flat,
  `LastSeen { location, date_text }` flat. All sub-models optional at
  top level for multi-turn intake support.
- Multi-language routing: caller passes `lang: str`. Single prompt
  template parameterized by `LANGUAGE_NAMES[lang]`. Per-language
  prompt files deferred unless probe data warrants.
- Matching algorithm: pure-Core two-stage. Jaro-Winkler ≥0.85 gate +
  composite ≥0.70 threshold. No LLM in matching path. Confidence
  bands (low/medium/high) per `MatchResult`.
- Source-script preservation as the transliteration bridge.
- Confidence band Q3 loosening: same-script exact + ≥1 corroborating
  → high (vs spec's ≥2).

### Open (active decisions for Bundle 1 planning gate)

These surface as Boss-mode questions when Bundle 1 starts. Not
pre-resolved.

- **SSE protocol choice:** raw FastAPI StreamingResponse, sse-starlette
  dependency, or asyncio-based generator?
- **Frontend state management:** plain useReducer, Zustand, or other?
- **Structlog → SSE bridge:** in-process structlog events added to the
  same SSE stream as audit events, or served as separate stream?
- **Reconnection strategy:** auto-reconnect with backoff, or manual
  reconnect? Demo needs deterministic behavior.
- **Beat 5 progressive-fill mechanism:** three sequential audio files
  (per Part 3 Issue 1) or SSE-side staggered rendering? ADR-004
  deferred this to Bundle 1.
- **Beat 7 `escalate_crisis` rendering:** synthetic-but-truthful tool
  entry tied to `crisis_detected` (recommended), or Gemma tool-call
  wrapper, or storyboard rewrite?
- **Beat 7 "semantic check" log line:** sidebar fake accepting current
  keyword-only reality, stubbed semantic emission, or defer?

---

## 8. Governance

This is how work actually gets done. Not a suggestion; a working
convention.

### Session pattern

- Every significant task runs in a **fresh Claude Code session.**
  Long sessions drift; fresh sessions stay sharp.
- Each session starts with a **read phase**: session reads relevant
  docs + code and answers (a)(b)(c)(d)-style questions before
  proposing a plan.
- **Plan approval before execution.** Session writes a plan; the
  strategy copilot audits; user (Mark) ratifies or tightens.
- **One job per session.** Phase 1 ran 6 sessions for distinct
  concerns: multilang sweep (S1), storage (S2), extraction (S3),
  orchestration (S4), matching trigger + audit verification + ADR
  (S5), smoke test (S6). Bundle 1 runs ~6 sessions on a similar
  decomposition.
- **Stop and flag beats silently fix downstream.** If a session's
  work surfaces issues in other files, it reports rather than
  spreading the edit.
- **Propagating strictness is healthy.** When one file becomes
  stricter and creates errors elsewhere, commit the win; let the
  next file resolve the new errors.

### Git discipline

- Commits are local by default.
- `git push` requires explicit "push it" instruction from user.
- One commit per session for clean rollback boundaries. Phase 1
  commits prefixed `phase-Sn:`. Bundle 1 commits prefixed
  `bundle1-Sn:`.
- Squash + push at natural save points.
- Commit messages follow Conventional Commits where meaningful.

### Decision hierarchy

1. User (Mark) — final authority on all decisions, especially
   framing, scope, and stop points
2. Strategy copilot (whichever Claude thread is active) — audits
   plans, flags risks, tracks governance, proposes options with
   tradeoffs, drafts briefs, answers Boss-mode questions
3. Claude Code sessions — execute approved plans, stop and flag
   on ambiguity, never push without explicit instruction

### Checkpoints (Boss-mode mandatory)

- **Phase 1 closure (May 1):** ✅ Runtime spine working.
- **Bundle 1 closure (~May 4):** UI affordances landed? SSE stream
  feeding sidebar? Demo recordable end-to-end?
- **50% checkpoint (May 8-9):** Submittable safety-net video exists?
  What should I cut for the remaining build window?
- **75% checkpoint (May 12-13):** LLM-judge score improving?
  Competitive differentiators identified and emphasized?

### Iteration caps

- Visual / polish iterations: **2-3 rounds then punt.** If round 3
  isn't clearly better than round 1, move on.
- Plan revisions: **2 rounds.** If a plan is still wrong on round 3,
  scope is probably miscalibrated, not the plan.
- Debug loops: **2 hours max without a stop-and-reflect.** If a bug
  eats 2 hours, that's a Boss-mode moment: is this still the right
  problem to solve?

---

## 9. Risks and failure modes (project-level)

See area charters (section 6) for area-specific risks. This section
tracks project-level failure modes that span multiple areas.

### Resolved (Phase 1 closure)

- **Runtime-spine gap (Day 11 finding).** Day 10 shipped Core
  components but no runtime pipeline — `match_records` had zero
  non-test callers; storage was a 1-line stub; FastAPI intake route
  emitted hardcoded stubs; no record-status enum, no match_link
  model. Phase 1 (Apr 27 – May 1, commits `9615bcd` → `bfa50e9`)
  closed the gap with the full runtime spine: storage layer,
  extraction tool-calling, ingest_audio orchestration, matching
  trigger, audit-event stream, end-to-end smoke gate. **RESOLVED
  May 1.** Documented for project-history retention because the
  finding itself is a useful "Challenges we ran into" entry per
  SKILL Phase 3.5 (Devpost writeup) — the kind of honest engineering
  story that builds judge trust.

### Known failure modes (already defended)

- **Gemma's audio path producing partial transcriptions presented as
  schema-valid output** — Farsi case discovered Day 10. Whisper caught
  all of it. Two-model pipeline eliminates this entire class.
- **Gemma's audio path silently ignoring `format=` under
  `think=False` (Issue #15260)** — empirically falsified Day 8.
  Refuted as a path; Whisper substituted as ASR.
- **Cross-script transliteration matching for leading-vowel-ambiguous
  names** — discovered Day 10 matching session. Resolved via
  source-script preservation: matching bridges Omar/Umar through
  shared Arabic canonical, not through Latin-string comparison.
- **Ollama ≤0.20.2 GGML crashes** — resolved by version pin ≥0.20.3.
- **Audio head-silence padding** — canonical adapter via ffmpeg.
- **25-second runaway loop** — adapter timeout, enforced by test.
- **39-minute degenerate Swahili repetition** — ruled out Swahili;
  defended by timeout.
- **Transliteration variance breaking matching** — solved by
  source-script preservation + fuzzy matching.
- **Crisis message handled as intake** — solved by crisis detection
  blocking extraction + matching at orchestration layer.
- **Gemma 4 E2B reasoning-mode trap** — Day 4 Session 4 discovery.
  Solved by `think=False` on every adapter call. ADR-003 records.
- **`asyncio.to_thread` cancellation scope** — Day 4 Session 4
  characterized. Core-time-only guarantee. Adapter design accepts
  this rather than fighting it.
- **Audio preprocessing as a tuning knob** — refuted across 5
  interventions Day 9 evening. Whisper sidesteps the question.
- **Gemma sampling parameters as a tuning knob** — refuted across
  5 interventions Day 9 evening. Not relevant to Whisper.
- **Smoke fixture content gap** — Day 11 prereq verification used
  `spanish_01.wav` (a restaurant phrase, not intake content). S6
  smoke test caught this on first run; re-pointed to TTS-generated
  Spanish intake clip. The fixture-gap finding is exactly what smoke
  tests are for — caught a real-world content mismatch the 118
  mocked tests couldn't catch by definition.

### Risks to watch

- **Bundle 1 SSE wiring slipping past May 4.** Mitigation: planning-
  gate Boss-mode questions resolved early, plan-approve-execute
  discipline per session, scope-cut willingness at S3 if behind.
- **Demo workstream still behind technical workstream.** Bundle 1 +
  Bundle 2 catch up the UI; safety-net video May 7-9 is the
  forcing function.
- **Scope creep after May 10 (feature freeze).** Mitigation: feature
  freeze is a hard rule; "just one more thing" is the enemy.
- **Tiredness-driven architectural changes.** Mitigation: no
  all-nighters, Boss-mode checkpoints, this document as reference
  when mid-build confusion hits.
- **Claude Code session context drift on long sessions.** Mitigation:
  fresh session per task; HANDOFF.md + this document as
  fresh-session reading material.
- **Devpost writeup written last-minute.** Mitigation: pre-pivot
  draft exists; Phase 6 (May 10-12) rewrites against the certified
  Phase 1 reality. LLM-as-judge Pass 1 (~May 6) forces writeup to
  exist early.
- **Beat 7 "semantic check" sidebar entry has no implementation
  backing it.** Bundle 1 Boss-mode question. Three options laid out
  in BUNDLE-1-CONTEXT.md.
- **Beat 7 `escalate_crisis(...)` rendering not backed by a real
  Gemma tool call.** Bundle 1 Boss-mode question. Recommended
  default: synthetic-but-truthful tool entry tied to
  `crisis_detected` audit event.
- **Fiverr audio late or unusable.** Mitigation: TTS Spanish exists
  and works; Mark can self-record if needed for safety-net.
- **Stub class proliferation in tests** (test_ingest_audio.py's
  _OllamaStub, test_matching_trigger.py's setup) is small but
  compounding. Worth a brief shared-test-fixtures pass during May
  10-12 polish window.

### Risks accepted but not mitigated

- **Judges not watching the full video.** Accepted: structure the
  video so the wow moment is at 1:30, not at 2:30. First 10 seconds
  carry the hook.
- **Another team submitting a similar idea.** Accepted: KIN's
  differentiation is architectural (layered, offline, tested) not
  conceptual. Competitive scan rounds 1 and 2 identify specific
  differentiators to emphasize.

---

## 10. Session budget

Original projection: ~55 Claude Code sessions across the build window.

Used through May 1 (post-Phase 1):

| Phase | Days | Sessions used |
|---|---|---|
| Pre-Day-3 planning | 0-2 | ~3 |
| Day 3 scaffolding | 3 | ~3 |
| Days 4-7 foundation | 4-7 | ~10 |
| Days 8-9 falsifications | 8-9 | ~8 |
| Day 10 Whisper pivot + Core completion | 10 | ~3 |
| Day 11 prereq verification + Apr 28 hello-world | 11-12 | ~3 |
| Phase 1 (S1-S6) | Apr 29 – May 1 | 6 |

Total used: ~36 sessions. Calendar elapsed: 11 of 17 build-window days
(65%).

Sessions projected ahead:

| Bundle | Window | Projected sessions |
|---|---|---|
| Bundle 1: SSE + UI affordances | May 2-4 | ~6 |
| Bundle 2: Tent A snapshot + smoke | May 5-6 | ~3-4 |
| Phase 4: safety-net recording | May 7-9 | ~1-2 (CC support) |
| Phase 6: polish + LLM-judge | May 10-12 | ~4-5 |
| Phase 7: final video production | May 13-15 | ~2-3 (CC support) |
| Phase 8: submission | May 16 | ~1 |

Projected total: ~36 + 17-21 = ~53-57 sessions. Tracking close to
original budget. The Phase 1 6-session burn was on-budget; Bundle 1's
6-session projection is the largest remaining bundle.

Risk: if Bundle 1 slips past 8 sessions, scope cuts begin (drop
affordance (a) merge animation polish first; drop affordance (d)
syntax highlighting next; keep (b) two-device + (c) structlog real
wiring as non-negotiable).

---

## 11. Bundle methodology (Phase 1 retrospective + working pattern)

This section documents the discipline that produced Phase 1 cleanly
across S1-S6. Carry into Bundle 1 and beyond.

### What worked, in priority order

1. **Cross-session decisions locked at planning gate.** IntakeRecord
   shape, audit-event mapping ownership, concurrency model, mapping
   rules — once decided in the brief, never relitigated. Saved hours
   of mid-session re-deciding.
2. **Pre-flight Boss-mode questions surfaced before each session.**
   Pydantic v2 probe before S2, source-vs-translation extraction
   before S4, file-placement before S5, fixture choice before S6.
   Each prevented a wrong-direction implementation. ~30 seconds to
   answer; cost of wrong answer mid-session would have been hours.
3. **Plan-approve-execute discipline.** Plan returned, Mark approves,
   agent executes, agent returns verdict. No silent decisions, no
   surprise commits. Course-correct between sessions, not after.
4. **Test budget caps in the brief.** Pulled discipline out of the
   brief, not relying on agent restraint. S2 hit 29 (with Clock
   surplus called out as expected), S3 hit 10, S4 hit 6, S5 hit 5,
   S6 hit 1 — all on the lower bound or with the surplus pre-flighted.
5. **ITEM E (audit-event mapping) as verification, not implementation.**
   Walking the table at S5 entry was the right move; mapping was
   satisfied incrementally across S2-S5. The verification was a final
   pass, not a separate implementation session.
6. **One commit per session.** Clean rollback boundaries. If S5 had
   broken something subtle, reverting `eeafcc4` alone would have
   worked without losing S2-S4.

### What to adjust in future bundles

- **S5 plan got long** because three concerns (matching trigger,
  audit verification, ADR-004) bundled together. Worth tighter
  session scopes when work has natural seams. Counter-argument: tight
  coupling here was real; a fourth session would have been ceremony.
- **Stub class proliferation** (test_ingest_audio.py's _OllamaStub,
  test_matching_trigger.py's setup) is small but compounding. Worth
  a brief shared-test-fixtures pass during May 10-12 polish window.

### Bundle structure (for Bundle 1+ to mirror)

Each bundle brief contains:

1. **Context** — what landed before, what the bundle ships, why now
2. **Cross-session decisions** — locked at planning gate, not
   relitigated
3. **Discrepancies / pre-flight resolutions** — anything the brief
   author already resolved
4. **Out of scope** — explicit list, prevents scope creep
5. **Per-session contracts** — S1..Sn with: scope, files, test count
   target, exit criteria, Boss-mode escalation triggers, commit
   message
6. **Deliverables list** — final flat list of all files touched
7. **Constraints** — reaffirmed (no git push, layer boundary,
   existing tests stay green, etc.)

Each session within the bundle:

1. Agent enters S1, reads relevant context
2. Agent returns a plan (file changes, test counts, pre-flight
   resolutions, exit criteria, escalation triggers, commit message)
3. Mark reviews; surfaces Boss-mode questions if needed; approves
4. Agent executes
5. Agent returns verdict (test counts, files changed, regressions,
   pre-flight resolutions held)
6. Mark approves S commit; agent commits locally
7. Repeat for next S

This shape is what enables a non-developer (Mark) to orchestrate a
solo hackathon build by managing one Claude Code thread per session
with a strategy thread holding cross-session context.

---

## 12. Reference map

Files in this repo:

- `HANDOFF.md` — durable cross-thread context, post-Phase-1 state,
  open questions for next agent
- `CLAUDE.md` — product spec, coding principles, scope exclusions
- `AGENTS.md` — Claude Code operating conventions
- `docs/test_strategy.md` — authoritative test strategy
- `docs/phase-5B-scaffolding.md` — directory tree and migration spec
- `docs/matching.md` — matching algorithm, thresholds, runtime trigger
  entry point §9
- `docs/architecture-diagram.{mmd,png}` — Devpost-quality system diagram
- `docs/architecture-diagram-legend.png`
- `docs/architecture-diagram-CHANGES.md`
- `docs/ADR/001-web-ui-primary-demo-surface.md`
- `docs/ADR/002-test-strategy-reconciliation.md`
- `docs/ADR/003-gemma-think-false.md`
- `docs/ADR/004-orchestration-architecture.md`

Files in the project folder (skill outputs from planning phases):

- `/mnt/project/phase-1-problem.md` through `phase-5_7-demo-script.md`
- `/mnt/project/schedule-30day.md` (historical; superseded by §4 of
  this doc as of Apr 27 re-plan)
- `/mnt/project/patterns.md`
- `/mnt/project/SKILL.md`

Strategy / brief artifacts:

- `briefs/bundle-1-context.md` (or wherever Mark places it) — Bundle 1
  spec material with Part 2 REV 3 verbatim, audit-event-to-UI
  mapping, provisional session breakdown, Boss-mode questions

Key commits (Phase 1):

- `9615bcd` — phase-S2: storage layer
- `cd82c3a` — phase-S3: ollama tool_call() + extract_intake_fields tool
- `c97f86e` — phase-S4: ingest_audio orchestration
- `eeafcc4` — phase-S5: matching trigger + ADR-004 + matching docs §9
- `2a48878` — phase-S6: Phase 1 smoke test infrastructure
- `bfa50e9` — phase-S6 followup: TTS fixture re-point + smoke GREEN
  (Phase 1 closure)

Earlier key commits:

- `acb60d6` — Block B.5 Session 1: primitives directory split
- `87454cc` — Day 3 Session 1: Python scaffolding
- `71919d9` — Day 3 Session 2: Clock Protocol + FakeClock + layer
  boundary
- `473424c` — Day 4 Session 1: SystemClock adapter
- `e1baa9d` — Day 5 Session 1A: OllamaAdapter skeleton + ADR-003
- `e3093bc` — Day 5 Session 1B: adapter behavior layer
- `bd9e734` — Day 6 Session 1: first-pass safety_rules
- `5306d1d` — Day 6 Session 2: GGML retry mechanism
- `7b0470a` — Day 6 Session 3: RFL schema expansion
- `1ddf88c` — Day 7 Session 1: Spanish language routing
- `8fa3715` — Day 7 Session 2: AR + FA language routing
- `76f3d24` — Day 10 Session 1: two-model pipeline (Whisper + Gemma)
- `31ee5d8` — Day 10 Session 2: multilingual safety_rules
- `4c4785b` — Day 10 Session 3: cross-record matching

---

## 13. Update discipline

This file is a living document. Update it:

- At the end of each phase / bundle (Phase 1 done, Bundle 1 done, etc.)
- At each checkpoint (Bundle 1 closure, 50%, 75%)
- When a locked decision changes (rare — requires Boss-mode reason)
- When a risk materializes or a new one surfaces
- When an area charter's "Definition of done" becomes met
- When the "Done" / "Locked" / "Open" sections would otherwise become
  stale

If this file and reality diverge, reality wins. Update same-day.

Last updated: May 1, 2026 — Phase 1 certified. Runtime spine landed
across six sessions Apr 27 – May 1. Six commits (`9615bcd` →
`bfa50e9`). Test count 75 → 119. Smoke gate green against real
Whisper + real Gemma. ADR-004 added. Bundle methodology section
captured as §11. Next major update at Bundle 1 closure (~May 4) or
at first material decision change.