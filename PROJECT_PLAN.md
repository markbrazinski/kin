# KIN — Master Project Plan

> Living document. Commit to repo root. Update at every checkpoint and
> major decision. If this file and reality diverge, reality wins and
> this file gets updated same-day.

Last updated: April 28, 2026 (Day 7 of 25) — end of Day 7. Five
Claude Code sessions across Days 6 and 7, all plan-approve-execute
shape with zero rework. Day 6 closed three commits (safety_rules
first-pass `bd9e734`, GGML retry + InferenceFailed `5306d1d`, RFL
schema expansion `7b0470a`). Day 7 closed two commits (Spanish
routing `1ddf88c`, Arabic + Farsi routing `8fa3715`). 40 tests
green, ruff clean. Adapter chapter complete: all 6 exception
classes have direct test coverage and all four §7-Locked languages
route through the adapter with language-aware prompts. Core layer
has safety_rules (English first-pass), language_matrix, and
expanded RFL schema. Day 8 opens against fully-tested wiring with
the manual probe (real-audio validation across en/es/ar/fa) as the
empirical reality check before Day 9-10's matching + FastAPI work.
Maintainer: Mark Brazinski (solo developer)
Next scheduled update: 25% checkpoint reflection (Day 7-8 boundary
— Day 8 opener should run the checkpoint), or end of Day 8 if
substantial work lands.

---

## 1. What we're building and why

**KIN** is an offline, multilingual family-reunification intake copilot
built for aid workers in low-connectivity field settings. It runs on a
laptop (MacBook Air M4, 16 GiB RAM) with no external network
dependency. It accepts voice intake in English, Spanish, Arabic, or
Farsi, produces structured records compatible with Primero and proGres
data shapes, and surfaces cross-session matches when the same missing
person appears in two aid workers' records under different
transliterations.

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

Three-layer hexagonal design. Enforcement is non-negotiable — a
CI test validates layer boundaries via AST import scanning (due in
Day 3 scaffolding).

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
│  - ollama_adapter (canonical ffmpeg padding,     │
│    25s timeout, structlog)                       │
│  - storage_adapter (JSONL)                       │
│  - sync_adapter (RFL-shaped JSON export)         │
│  - system_clock (Clock Protocol impl)            │
│  - May import from Core only                     │
│  - Never imports from UI (upward forbidden)      │
│  - Makes zero business decisions                 │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│  Core layer (src/core/)                          │
│  - Pure Pydantic schemas (RFL record shape)      │
│  - Safety rules (crisis detection, minor        │
│    routing)                                      │
│  - Matching logic (phonetic + corroborating     │
│    fields + threshold)                           │
│  - Scoring functions                             │
│  - Language matrix                               │
│  - Clock Protocol (implementations live in      │
│    Integration)                                  │
│  - Zero I/O. No network, no disk, no model      │
│    calls.                                        │
│  - Fully testable without any external           │
│    dependency                                    │
└──────────────────────────────────────────────────┘
```

### Why this architecture

Three reasons, each doing real work:

**1. Testability.** Core is pure — unit tests run in milliseconds with
no fixtures, no network mocks, no model calls. Integration tests use
stub clients at the adapter seam. UI is dumb and orchestrated through
Core.

**2. Demo reliability.** If Ollama hangs (it has — we saw a 39-minute
runaway loop on Swahili), the adapter's 25-second timeout contains
the damage and Core's fallback paths take over. A demo machine never
hangs on stage.

**3. Defensibility against "it's just a Gemma wrapper."** Judges who
ask "what did you build besides call Gemma?" can point to the Core
layer: safety rules, matching logic, scoring, invariants. Gemma is
one service call inside a larger reasoning system.

### Key technical locks

- Model: **Gemma 4 E2B** (NOT E4B, NOT 26B, NOT 31B). E2B runs
  comfortably on 8–16 GB field-hardware. E4B crashes Ollama ≤0.20.2
  with GGML errors and barely fits on the demo machine.
- Languages: **EN / ES / AR / FA only.** Nine evaluated during Phase
  2.5; five ruled out for coverage, fixture availability, or
  fine-tuning inconsistency.
- Matching: source-script exact + transliteration fuzzy (Jaro-Winkler
  ≥0.85) + corroborating fields scored against ~0.7 threshold.
  Human-in-the-loop confirmation, no auto-merge, **no LLM in the
  matching path.**
- Audio: ffmpeg head-silence padding required before inference;
  canonical adapter owns this.
- Timeouts: 25 seconds per inference call, enforced by adapter via
  FakeClock-driven tests (docs/test_strategy.md §8).

---

## 4. The 25-day arc

```
Day  0  ┌─ Planning (Phase 0-5)          ← DONE April 23
Day  1  │   Phase 3 UI migration         ← DONE April 24 (Block B)
Day  2  │   Block B.5 complete           ← DONE April 24 EOD
        │     - primitives/ split (acb60d6)
        │     - lib/types.ts extracted
Day  3  └─   Python scaffolding + Core layer start   ← DONE
Day  4  ┌─ Foundation                     ← DONE (Apr 25)
Day  5  │   Gemma hello-world, first audio pipeline,  ← DONE (Apr 26)
Day  6  │   test environment, core data model,        ← DONE (Apr 27)
Day  7  │   25% checkpoint ★                          ← DONE (Apr 28)
Day  8  └─
Day  9  ┌─ LLM-as-judge Pass 1 ✱         (Devpost draft + progress)
Day 10  │
Day 11  │
Day 12  │  Core features
Day 13  │   4-language audio, RFL schema solid,
Day 14  │   safety rules, matching logic, SSE replaces
Day 15  │   setTimeout sequencer
Day 16  └─
Day 14  ★ RECORD SAFETY-NET VIDEO — tag safety-net-v1
Day 16  ★ FEATURE FREEZE — 50% checkpoint

Day 17  ┌─ Polish + Evidence
Day 18  │  LLM-as-judge Pass 2 ✱         (full submission)
Day 19  │  demo artifacts live, README, audit tools
Day 20  └─   list, final end-to-end on clean data

Day 21  ┌─ Demo + Content
Day 22  │  LLM-as-judge Pass 3 ✱         (judging-experience
Day 23  │                                  simulation)
Day 24  │  VO script, demo coach, record 3 takes,
Day 25  │  edit, upload, finalize Devpost
        │  ★ SUBMIT May 17 (Day 24)
        │  May 18: deadline buffer, touch nothing
        └─
```

★ = milestone / gate
✱ = LLM-as-judge pass

### Day 8 scope (next session)

Day 8 opens with the empirical reality check the routing layer has
been waiting for. Day 7 closed with all four §7-Locked languages
routing through the adapter via `_build_prompt(lang)` — but no
real audio has gone through the canonical adapter at `think=False`
yet. The Day 4 bridge proved English; Phase 2.5 Farsi data was
collected with reasoning mode on at `num_predict=1500` (the trap-
masking value). Today's adapter at `num_predict=400` with
`think=False` against AR/FA real audio is empirically untested.

Day 8 has two prioritized deliverables:

**1. Manual probe script — `scripts/probe_multilang.py`.** Runs
real audio samples (`audio_samples/english_01.wav` plus three
new short clips for ES/AR/FA) through the canonical
`OllamaAdapter` at `think=False` with the language-aware prompt
and records latency, eval_count, done_reason, and content shape
per language. Output: a results file similar to
`results/farsi_retest_summary_20260423_084616.md` covering all
four languages. This is the Walk tier of the crawl-walk-run
multilingual story (per Day 7 opener Boss-mode discussion). If
AR/FA produce broken transcription, that's where we discover it
and decide whether per-language prompt files become a Day 11+
necessity. Estimated 1 session, plus 30-45 min of human time
finding/recording audio samples (probably 5-10s each). 25%
checkpoint reflection lands at the start of this session before
the probe runs.

**2. Multilingual safety_rules expansion.** Day 6 Session 1 left
`safety_rules` as English-only with TODO markers for ES/AR/FA.
A Spanish speaker in crisis must be detected. This session
opens with Boss-mode questions about (a) crisis keyword sets
per language — humanitarian agencies have published lists, but
which sources, (b) Latin-script `.lower()` vs Arabic-script
case behavior (Arabic/Persian have no concept of case;
substring match still works but `.lower()` is a no-op), (c)
whether RTL languages need different keyword storage. Estimated
1 session after questions answered.

Explicitly **not** Day 8 scope (pushed to Day 9+):
- Matching logic (Jaro-Winkler + corroborating fields) — Day 9-12
- FastAPI + SSE routes — Day 9-10
- Live microphone capture — Day 10+
- UI changes — Day 12-15 SSE-replaces-setTimeout window
- Per-language prompt files — Day 11+ if probe data warrants
- Semantic crisis detection via Gemma — Day 9-12 if time

Day 8 is also the **25% checkpoint** per `§4` arc. Boss-mode
question to answer at session opening: "Am I building the demo or
adding features? What should I cut for the remaining 18 days?"
Honest answer at Day 7 EOD: routing infrastructure is complete
and tested but unproven against real audio. The probe is THE
critical-path empirical work between today and Day 13's safety-
net video recording. If the probe surfaces broken AR/FA behavior
that requires multi-day prompt iteration, the multilingual demo
story may need to compress.

### Why these specific dates

- **Day 14 safety-net video** is 47% of the window, not 50%. Gives
  buffer if recording reveals problems.
- **Day 16 feature freeze** is before the final third of the
  schedule. After feature freeze: only fixes, polish, and content.
  Adding features in the final third is how solo hackathons die.
- **Three LLM-as-judge passes** instead of two because the third pass
  simulates judging experience (tired judge, 90 seconds per project,
  muted mobile playback) rather than criterion scoring. Costs ~2
  hours, genuinely additive.
- **May 17 submit** gives one full day of buffer. Every year,
  someone's internet goes out on deadline day.

---

## 5. Why each area gets investment

Investment allocation follows the "judges watch the video, not the
code" principle. Percentages are approximate effort, not hours.

| Area | Effort % | Why |
|---|---|---|
| Planning + architecture | 10% | Foundation; wrong architecture makes everything else harder |
| UI migration + scaffolding | 15% | The demo happens in this UI; it must be real, not mocked |
| Gemma integration + audio | 20% | Core technical risk; failure here kills demo |
| Core logic (safety, matching, scoring) | 20% | Defensibility; the "what did you build besides call Gemma" answer |
| Testing (~100-150 meaningful tests) | 10% | Reliability for the demo; also signals engineering rigor to judges |
| Devpost writeup + evidence | 10% | First filter judges see; must be done well |
| Demo video production | 15% | The artifact judges actually score; 10 min raw → 2:20 final |

### Investment rationale per area

**Planning got heavy investment because solo hackathons fail by
building the wrong thing, not by building the right thing badly.**
Phase 0-5C consumed a full day and produced: architecture, test
strategy with pushback, framing (hero + persona + narrator), prize
strategy, and a prototype audit. The alternative — start coding on
Day 1 — produces technically-correct projects that don't land with
judges.

**UI migration is real engineering, not polish.** The Vite + React +
TypeScript + Tailwind stack is the substrate for the entire demo
video. Typing it properly under strict mode (Block B) took ~10
sessions and zero behavior change; splitting primitives and lifting
shared types (Block B.5) took 2 more sessions with the same zero-
behavior-change bar. It's the foundation that Gemma integration
(Day 3+) will call into via SSE.

**Gemma integration is where reality pushes back.** Phase 2.5
surfaced: Ollama ≤0.20.2 GGML crashes, audio head-silence padding
requirements, 25-second timeout budget, 39-minute runaway loop on
Swahili. These are already codified in the adapter spec. Expect more
surprises Day 3-7.

**Core logic is the defensibility lever.** "It's just a wrapper" is
the dismissal every Gemma-hackathon submission fears. Safety rules
(crisis detection blocking RFL tool calls in 4 languages), matching
logic (phonetic + corroborating fields, no LLM in the path), and
Clock Protocol testing are what separate KIN from a chat UI over
Gemma.

**Tests earn investment at ~100-150 meaningful, not 500 theatrical.**
Per docs/test_strategy.md: invariant-first (crisis blocks RFL,
minor forces Guardian, 25s timeout fires), not count-first. A judge
who reads the test directory will notice either the invariants
landing or the absence of them. Test count alone is noise.

**Devpost writeup and evidence get 10% because judges skim it
before deciding to watch the video.** A muddy writeup means the
video never gets watched. A sharp writeup earns 3 minutes of
attention and the video does the rest.

**Demo video production gets 15% because the video IS the
artifact.** For online hackathons, judges never run code. They
watch videos. Phase 5.7 is a full production pass: VO script, demo
coach review, 3 recording takes, editing, B-roll. 10 minutes of raw
footage becomes 2:20 of final video.

### What doesn't get investment

Equally important: what KIN is deliberately NOT spending time on.

- **A general-purpose chat UI.** KIN is intake, not conversation.
- **More than 4 languages.** Coverage beyond EN/ES/AR/FA was
  evaluated and ruled out.
- **Cloud storage, sync, or multi-device.** Offline-first, laptop-only.
- **Fine-tuning Gemma.** Out-of-the-box E2B is sufficient; the
  fine-tuning surface is another whole project.
- **Real photo intake (photo matching).** Placeholder in UI; feature
  stubbed, not built.
- **OCR, handwriting, barcode.** Voice intake only.
- **Production-grade auth, user management, audit logs beyond
  structlog.** The demo is a single field laptop; multi-user is out
  of scope.

If an idea surfaces during build that doesn't fit these constraints,
the answer is no — regardless of how good the idea is — unless it's
both load-bearing for the demo AND achievable in < 4 hours.

---

## 6. Area charters

Each charter is self-contained. A new agent can read any one charter
and know what that area is, what it produces, what "done" looks like,
what's already decided, and what to watch for.

---

### 6.1 Planning + architecture

**Goal:** Ensure the project solves a problem that a tired judge at
10 PM cares about, using an architecture that survives reality checks
during build.

**Deliverables (all complete as of April 24):**
- Phase 0-5C planning documents in `/mnt/project/phase-*.md`
- Framing lock: "aid-worker copilot for intake, feeds Primero/proGres-shaped records"
- Narrator, hero, persona, beneficiary identified and distinct
- Architecture Decision Records in `docs/ADR/`
- `docs/test_strategy.md` with invariant-first testing strategy
- `docs/phase-5B-scaffolding.md` with directory tree and migration plan
- Prize strategy covering primary ($10K Digital Equity) + secondary
  categories
- This `PROJECT_PLAN.md` document (tracked as of Day 2)

**Definition of done:**
- All locked decisions ratified and documented
- No scope ambiguity remains on what KIN is and isn't
- Architecture is testable in isolation (layer boundary test due in
  Day 3 Python scaffolding)
- ✅ Done

**Key decisions already made:**
- Hexagonal three-layer architecture (Core / Integration / UI)
- Gemma 4 E2B as the model
- EN/ES/AR/FA as the language set
- 25-second adapter timeout
- Web UI as primary demo surface (ADR-001)
- Git: local-only commits, push requires explicit instruction
- Three LLM-as-judge passes (not two)

**Risks specific to this area:**
- Planning documents going stale as reality diverges. Mitigation:
  update this PROJECT_PLAN.md at every checkpoint.
- Decisions getting re-litigated mid-build because no one remembers
  they were made. Mitigation: section 7 of this doc tracks "Locked /
  Open / Done" state explicitly.

---

### 6.2 UI migration + scaffolding

**Goal:** Produce a production-grade, TypeScript-typed, strict-mode
React app that serves as the substrate for the demo video and hosts
the real SSE stream from the Python backend when it lands.

**Deliverables:**
- Vite + React + TypeScript + Tailwind project under `src/ui/web/`
  — ✅ done
- All 6 prototype files converted to TypeScript (icons.tsx,
  primitives.tsx, RecordCard.tsx, CrisisAndTranslit.tsx, DevTrace.tsx,
  App.tsx) — ✅ done (Block B)
- Whole-tree `tsc --noEmit` green — ✅ done and preserved through B.5
- Exported prop types for cross-file consumption — ✅ done
- Block B.5 primitives/ split: per-primitive files under
  `src/ui/web/src/components/primitives/` with index.ts barrel
  — ✅ done (commit `acb60d6`)
- Block B.5 lib/types.ts: cross-file data shapes consolidated
  (Language, MatchPhase, RecordData, NameVariant, GuardianData,
  TraceCall, CompletenessSegment) — ✅ done (Day 2 EOD)
- Real SSE client (replaces `setTimeout` demo sequencer) — ⏳ Core phase
- Six audit fixes applied (darken muted, link-draw animation, ⌘.
  shortcut, Noto Sans Arabic weights, storyboard-aligned match
  scenario, crisis paused overlay) — ✅ done
- Y-shape match beat anchored to match card — ✅ done

**Definition of done:**
- Whole-tree tsc green — ✅ done
- Block B.5 splits complete — ✅ done
- `lib/types.ts` consolidated — ✅ done
- Real SSE replacing setTimeout sequencer — ⏳ Core phase
- All four demo beats render correctly in AR/EN/ES/FA —
  ✅ done (intake, match, crisis, reset)

**Key decisions already made:**
- `type` not `interface` for props
- No `React.FC`
- Strict mode on from day one
- forwardRef pattern: `forwardRef<HTMLElement, PropsType>`
- `icon` props typed as `ReactNode` (matches JSX usage, not callable)
- Dual-mode view: Field mode default, Developer mode via ⌘D
- ⌘. shortcut + visible close button for demo dock (keyboard
  unreliable in some browsers)
- Web UI as primary demo surface, not CLI fallback (ADR-001)
- Per-primitive-file organization under primitives/ directory with
  index.ts barrel (Block B.5 Session 1)
- Cross-file data shapes live in `src/ui/web/src/lib/types.ts`;
  component prop types stay colocated with their component (Block
  B.5 Session 2)
- `lib/types.ts` is the UI-layer's view of data; Core's Pydantic
  schemas will mirror it on the Python side and reconcile at the
  integration boundary

**Risks specific to this area:**
- Vite HMR drift on long sessions (observed Day 1). Mitigation:
  hard refresh browser after significant edits; fresh Claude Code
  sessions per file.
- Browser intercepting keyboard shortcuts (Cmd+Period closes tabs in
  some browsers). Mitigation: close button on demo dock as primary
  affordance; shortcut as power-user.
- SSE replacement breaking demo timing. Mitigation: keep the
  `setTimeout` sequencer around as a dev-mode fallback until SSE is
  proven stable.
- `lib/types.ts` drifting from Core's Pydantic schemas once Core
  lands. Mitigation: header comment flags the mirror relationship;
  integration-layer adapter to be built when Core schemas stabilize.

---

### 6.3 Gemma integration + audio pipeline

**Goal:** Reliably run Gemma 4 E2B for voice intake across four
languages, producing structured intake records without hanging,
crashing, or looping — on a 16 GiB MacBook Air.

**Deliverables:**
- `src/integration/ollama_adapter.py` — canonical adapter with:
  - ffmpeg head-silence padding before every inference call
  - 25-second timeout via Clock Protocol (FakeClock in tests)
  - structlog structured logging of every call
  - Retry logic on transient failures
  - Fallback pathway when inference fails
- Audio pipeline: microphone → ffmpeg pad → Gemma → structured output
- Language detection (first few seconds of audio)
- Structured output parsing: Pydantic validation on every Gemma
  response
- Prompt templates per intake section (biographic, last-seen,
  distinguishing marks, guardian, completion)
- Fixture capture (Day 5-7, after prompts stabilize)

**Progress markers (Day 7 EOD):**
- `src/integration/system_clock.py` — ✅ done (Day 4 Session 1,
  commit `473424c`)
- `scripts/gemma_hello.py` — ✅ done (Day 4 Session 4,
  commit `6a45326`, findings docstring at `12b38d5`).
  Superseded by canonical adapter; retained as bridge evidence.
- `src/integration/ollama_adapter.py` — ✅ adapter chapter complete.
  Day 5 landed skeleton + behavior layer (Sessions 1A `e1baa9d` +
  1B `e3093bc`). Day 6 Session 2 `5306d1d` added the GGML retry
  mechanism (`(ollama.ResponseError, ollama.RequestError)` retry
  tuple) and gave `InferenceFailed` direct test coverage. Day 7
  Sessions 1+2 (`1ddf88c`, `8fa3715`) extended the adapter to
  accept a `lang: str = "en"` parameter, gate on
  `is_implemented(lang)` via Core's `language_matrix`, and route
  all four §7-Locked languages through the same `_build_prompt(lang)`
  template via `cast(SupportedLang, lang)` at the call site. ALL 6
  exception classes have direct test coverage:
  `PaddingUnavailable`, `PaddingFailed`, `InferenceTimeout`,
  `InvalidToolCall`, `InferenceFailed`, plus `AdapterError` base
  via inheritance, plus the new `UnsupportedLanguage` for
  unimplemented language values. structlog base payload includes
  `lang`. Routing layer: 5 stub-test coverage tests across
  `test_ollama_adapter_languages.py`. NOT yet validated against
  real audio in any language other than English (Day 8 manual
  probe).
- `src/core/language_matrix.py` — ✅ done (Day 7 Sessions 1+2).
  `SupportedLang` Literal covers en/es/ar/fa per §7 lock;
  `IMPLEMENTED_LANGS` frozenset covers all four; `LANGUAGE_NAMES`
  dict for prompt construction; `is_implemented(lang)` helper.
  Pure Core: stdlib + typing only. 2 tests in
  `tests/core/test_language_matrix.py`.
- `src/core/rfl_schema.py` — ✅ partial RFL record landed (Day 6
  Session 3 `7b0470a`). Full shape: `TranscriptionResult` (Day 5,
  unchanged) + `Name` (canonical + source_script Literal +
  transliterations) + `Age` (value + confidence Literal) +
  `LastSeen` (location + date_text, both free-text) + `Guardian`
  (present + consent, flat audit fields, no validators) +
  `RFLRecord` (top-level with all sub-models optional for
  multi-turn intake support). Field-level docstrings on every
  field. 3 structural tests in `tests/core/test_rfl_schema.py`.
  Single growing model per §7 versioning lock.
- `src/core/safety_rules.py` — ✅ first-pass English keyword
  detector (Day 6 Session 1 `bd9e734`). 9 phrases across self-harm
  / harm-to-others / immediate-danger categories. Non-EN langs
  return `is_crisis=False` with TODO marker pending Day 8
  multilingual expansion. 3 tests including case-insensitive
  matching. 5000-char defensive cap on input.
- `docs/ADR/003-gemma-think-false.md` — ✅ done (Day 5 Session 1A,
  `e1baa9d`). Records the `think=False` decision with provenance.
- Day-1 anchor timeout test — ✅ done. FakeClock-driven, sub-
  millisecond deterministic verification of the 25s cancellation
  race. `tests/integration/test_ollama_adapter_timeout.py`.
- Gemma 4 E2B runtime behavior characterized: reasoning mode is
  the default and must be disabled via `think=False`; audio
  encoder works cleanly; pre-M5 Metal buffer errors on stderr
  are benign (GGML logs them but inference succeeds).
- `asyncio.to_thread` cancellation documented as Core-time-only
  guarantee; daemon-side computation continues invisibly after
  `call.cancel()`. Adapter's `InferenceTimeout` docstring carries
  this language; structlog `inference_timeout` event records
  `elapsed_s` rather than claiming the daemon stopped.
- Ollama daemon version 0.21.0 confirmed working; Python SDK
  `ollama==0.6.1` (distinct semver track from daemon).
- Phase 2.5 probe surface fully assessed (Day 4 Session 3).
  Canonical ffmpeg filter at `scripts/test_audio_smoke.py:32-43`
  was lifted into `OllamaAdapter._preprocess` Day 5.
- Real-audio multi-language validation: starts Day 8 via
  `scripts/probe_multilang.py`. The crawl-walk-run framework: today's
  routing is "crawl"; the probe is "walk"; the demo recording at
  Day 13-15 is "run."

**Definition of done:**
- Hello-world: record 5 seconds of audio, get transcription, parse
  into RFL fields — works in all 4 languages
- 20 successful end-to-end runs in a row on at least one language
  (typically EN)
- Timeout test fires reliably (FakeClock-driven, in test suite)
- Structured output validates against RFL schema > 95% of the time;
  fallback catches the other 5%
- No runaway loops observed in red-team suite

**Key decisions already made:**
- Gemma 4 E2B, not E4B or larger
- Ollama ≥ 0.20.3 (lower versions crash)
- ffmpeg head-silence padding is non-negotiable
- 25-second timeout budget (source: 39-minute Swahili runaway
  observation)
- No fine-tuning; out-of-the-box model
- Clock Protocol in Core, SystemClock in Integration (testable via
  FakeClock)

**Risks specific to this area:**
- Gemma hallucinating structured output fields. Mitigation: Pydantic
  validation + field-level fallbacks.
- Audio issues (device permissions, sample rates, mic differences).
  Mitigation: test on demo hardware early (Day 5-6).
- Multilingual inference quality variance (AR/FA weaker than EN).
  Mitigation: red-team suite covers all four languages; fallback
  paths where confidence is low.
- Cold-start model loading time bloating demo recordings. Mitigation:
  pre-warm model before recording takes.

---

### 6.4 Core logic (safety, matching, scoring)

**Goal:** Provide the defensibility layer that separates KIN from
a Gemma chat wrapper — the logic that runs before, around, and after
every model call, enforcing invariants the model alone can't.

**Deliverables:**
- `src/core/rfl_schema.py` — Pydantic v2 models for the RFL record:
  Name (with source script + transliterations), Age, Relationship,
  LastSeen (location + date), Guardian (present + consent),
  DistinguishingMarks  _(landed Day 6 Session 3 `7b0470a`: 6 models
  total — `TranscriptionResult` + `Name` + `Age` + `LastSeen` +
  `Guardian` + `RFLRecord`. Field-level docstrings throughout.
  Single growing model per §7 versioning lock. Cross-field
  validators for minor-detection deferred to Day 8 multilingual
  safety expansion.)_
- `src/core/safety_rules.py` — `classify(text, lang) -> SafetyResult`
  with crisis detection (keyword + semantic paths) for all 4
  languages  _(docstring stub as of Day 3 EOD)_
- `src/core/matching.py` — phonetic matching (Jaro-Winkler ≥ 0.85)
  + corroborating field scoring + 0.7 threshold + no-LLM guarantee
  _(docstring stub as of Day 3 EOD)_
- `src/core/scoring.py` — tool-call confidence scoring
  _(docstring stub as of Day 3 EOD)_
- `src/core/language_matrix.py` — supported languages, routing logic
  _(docstring stub as of Day 3 EOD)_
- `src/core/clock.py` — Clock Protocol for deterministic time
  — ✅ **done (Day 3,** commit `71919d9`**)**
- `docs/matching.md` — matching spec (due before Day 6)

**Definition of done:**
- Three Day-1 anchor tests green:
  - Crisis blocks RFL tool call (4 langs × keyword + semantic paths)
  - Minor (age < 18) forces Guardian schema presence
  - 25-second adapter timeout fires via FakeClock
- Matching red-team suite covers: identical names (easy), phonetic
  variants (Mohammed/Mohamad), source-script identical but
  transliterations differ (Omar/Umar), similar names but different
  people (should NOT match), different scripts entirely (EN name +
  AR script — should NOT match on script alone)
- All Core modules have 95%+ coverage
- `tests/test_layer_boundaries.py` passes (Core imports nothing from
  Integration or UI)

**Key decisions already made:**
- Matching threshold: 0.7
- Jaro-Winkler threshold: 0.85 for phonetic
- No LLM in matching path — phonetic + rules only
- Human-in-the-loop confirmation, no auto-merge
- Crisis detection runs BEFORE RFL tools are made available
- Minor routing blocks completion until Guardian block is attempted
- Pydantic v2 (not v1)
- Source script preserved alongside transliterations — never
  normalized away

**Risks specific to this area:**
- Matching being too aggressive (false positives — merging records
  that aren't the same person). Mitigation: high threshold, human
  confirmation, corroborating fields required, no auto-merge.
- Matching being too conservative (false negatives — missing real
  matches). Mitigation: fuzzy phonetic matching, weighted corroborating
  field scoring, source-script exact matching catches cases phonetic
  alone misses.
- Crisis detection false negatives (missing a crisis message and
  allowing RFL tool calls). Mitigation: keyword pass + semantic pass
  + err on side of over-triggering; red-team suite with 10+ crisis
  cases across 4 languages.
- Age parsing edge cases (age in one language, age as range "around
  10", age as date of birth). Mitigation: Pydantic validator with
  explicit handling, fallback to "unknown, minor: unknown" routing.

---

### 6.5 Testing

**Goal:** Produce a test suite that demonstrates reliability to
judges, catches regressions during development, and proves the core
invariants hold.

**Deliverables:**
- 3 Day-1 anchor tests (Core, as above)
- 1 layer boundary test (AST import scanner)
  — ✅ **done (Day 3,** commit `71919d9`**):**
  `tests/test_layer_boundaries.py` with positive + negative cases
- `tests/fakes/fake_clock.py` — FakeClock implementation per
  test_strategy §5 (heapq-backed sleep queue, async `tick()`)
  — ✅ **done (Day 3,** commit `71919d9`**)**
- ~40-60 Core unit tests (pure logic, sub-millisecond)
- ~20-30 Integration tests at adapter seam (stub clients, no network)
- ~10-15 UI component tests (Vitest + Testing Library, no browser)
- ~10 red-team cases (crisis, minor, runaway loop, matching edge
  cases, adversarial inputs)
- Fixture manifest with prompt-hash staleness detection
- CI configuration: `pnpm typecheck`, `pytest`, layer boundary test

**Definition of done:**
- ~100-150 meaningful tests (not 500 theatrical)
- All 3 Day-1 anchors green
- Layer boundary test green
- Red-team suite green
- CI runs all tests in < 2 minutes on laptop
- Coverage: Core ≥ 95%, Integration ≥ 80%, UI ≥ 60%

**Key decisions already made:**
- Invariant-first, not count-first
- FakeClock in Python, `vi.useFakeTimers` in React (no Provider)
  — FakeClock ✅ implemented Day 3 at `tests/fakes/fake_clock.py`
- Zero real API calls in tests (all external I/O mocked)
- Fixtures captured Day 5-7 only (after prompts stabilize; earlier
  capture wastes staleness-detection mechanism)
- Red-team suite is separate from regression suite — red-team tests
  what we WANT to fail if invariants break
- Python test runner: `pytest` with `asyncio_mode = "auto"`, ruff
  clean (locked Day 3 as part of pyproject scaffolding)

**Risks specific to this area:**
- Fixture staleness as prompts evolve. Mitigation: prompt-hash in
  fixture manifest, test fails if hash changes without fixture
  refresh.
- Tests passing but demo still broken (missing integration coverage).
  Mitigation: at least 3 full end-to-end tests on real hardware
  before feature freeze.
- Test suite bloat (writing tests for test's sake). Mitigation:
  every test must name the invariant it enforces; if no invariant,
  delete.

---

### 6.6 Devpost writeup + evidence

**Goal:** Land a Kaggle writeup that earns a judge's 3 minutes of
video-watching time, and make KIN's claims verifiable with clickable
evidence.

**Deliverables:**
- Kaggle submission writeup (Devpost agent drafts, user reviews)
- Headline statistic, prominently placed: "Preserves source script
  across 4 languages; matches two transliterations of the same person
  across intake sessions"
- Per-prize category "why this wins" paragraphs (Digital Equity +
  secondary categories)
- Reframe applied: "aid-worker copilot for intake, feeds
  Primero/proGres-shaped records"
- Evidence bundle: architecture diagram, test coverage snapshot,
  red-team suite results, fixture manifest
- README.md at repo root for judges who click through
- Link to demo video (unlisted YouTube)
- Link to GitHub repo (public)

**Definition of done:**
- Writeup passes LLM-as-judge Pass 1 (Day 9) with weakest-criterion
  improvements applied
- Writeup passes LLM-as-judge Pass 2 (Day 17-18) with full submission
- Writeup survives "tired judge, 90 seconds" test from Pass 3 (Day 21)
- Headline stat in first paragraph, verifiable
- No hand-waving claims; everything backed by code or test

**Key decisions already made:**
- Devpost agent produces the draft; Mark reviews, doesn't author
- Three LLM-as-judge passes for iteration
- Reframe is non-negotiable — the aid-worker framing wins over
  solo-humanitarian-tool framing
- Evidence is clickable where possible, not just described

**Risks specific to this area:**
- Writeup written as afterthought (common failure mode). Mitigation:
  Pass 1 at Day 9, before most build work is done — forces writeup
  to exist early.
- Claims the demo can't back up. Mitigation: writeup and demo
  production share the same evidence bundle; they're reviewed
  together.
- Hackathon fatigue producing a flat, humble writeup. Mitigation:
  LLM-as-judge Pass 3 specifically evaluates "would a tired judge
  click play" — catches flatness.

---

### 6.7 Demo video production

**Goal:** Produce a 2:20 (±10s) demo video that lands "One child.
Found." within the first 90 seconds and survives muted mobile
playback.

**Deliverables:**
- Storyboard (locked) with all four beats: intake, match, crisis,
  reset
- VO script (Phase 5.7 output)
- Safety-net video recorded Day 14, tagged `safety-net-v1`
- Final video recorded Day 22-23, 3 takes minimum
- Edit: B-roll, visual polish, captions (English + target languages
  where relevant)
- Upload to YouTube (unlisted)
- Thumbnail that works at Kaggle gallery size

**Definition of done:**
- Safety-net video exists by Day 14 (non-negotiable)
- Final video: 2:20 (±10s), wow moment at 1:30, hook survives first
  10 seconds muted
- All four beats render correctly in the video
- Audio levels consistent, no clipping, no background noise
- Captions present and accurate
- Uploaded, unlisted, linked from Kaggle submission
- Pass 3 LLM-as-judge approves the video independently of the writeup

**Key decisions already made:**
- Target length: 2:20 (not 3:00, not 1:00)
- Wow moment placement: 1:30 mark
- Narrator voice: Principal PM at Twilio
- Hero: displaced parent
- Demo moment: transliteration match — "One child. Found."
- Safety-net video is a contract, not a nice-to-have
- Final video uses storyboard + VO script; no improvisation on
  recording day

**Risks specific to this area:**
- Recording day technical failures (audio, screen capture, Gemma
  model not loading). Mitigation: safety-net video exists 10 days
  earlier; final recording has 3 takes; pre-flight checklist.
- Video too long (common failure mode). Mitigation: strict 2:20
  target; if a beat can't fit, cut the beat, not the length.
- Video reveals demo is brittle. Mitigation: hardening phase (Day
  13-16) includes 10 end-to-end runs; if less than 9/10 succeed,
  don't record yet.
- Audio quality issues. Mitigation: test microphone Day 13, borrow
  better mic if needed, re-record audio separately from screen
  capture if quality is uneven.

---

## 7. What's done, what's locked, what's open

### Done (as of April 24, 2026 — Day 2 EOD)

- Phase 0-5C planning (all framing, architecture, test strategy,
  prize strategy documents)
- UX research synthesis (Opus + Gemini bake-off on field UX for
  humanitarian intake tools)
- Prototype received from Claude Design, audited, 3 audit fixes
  identified
- Phase 3 Block A: 6 audit fixes + 2 prime fixes + 3 rounds of match
  beat polish → Y-shape linking anchored to match card
- Phase 3 Block B: TypeScript conversion across 6 files, whole-tree
  `tsc --noEmit` green, zero runtime behavior changes
- **Block B.5 Session 1** (Day 2): primitives.tsx split into
  per-primitive directory + index.ts barrel (commit `acb60d6`)
- **Block B.5 Session 2** (Day 2 EOD): lib/types.ts created, 7
  cross-file data shapes consolidated (Language, MatchPhase,
  RecordData, NameVariant, GuardianData, TraceCall,
  CompletenessSegment), 5 importers updated, primitives barrel
  pruned, zero runtime behavior change, all four demo beats verified
- **Day 3 Python scaffolding** (Day 3 EOD):
  - Python env stood up from zero: uv + setuptools + ruff,
    `pyproject.toml` under src/ layout, smoke test green
    (commit `87454cc`)
  - `src/core/` and `src/integration/` created with docstring-stub
    modules (no implementation yet except clock.py)
  - `src/core/clock.py` Clock Protocol per test_strategy §5:
    `@runtime_checkable`, `monotonic() -> float`, async `sleep()`
  - `tests/fakes/fake_clock.py` FakeClock: heapq-backed sleep queue,
    async `tick()` to advance virtual time deterministically
  - `tests/test_layer_boundaries.py` AST import scanner: Core imports
    nothing from Integration or UI, with negative tests proving the
    scanner catches violations
  - 16 tests passing in 0.02s, ruff clean (commit `71919d9`)
  - Phase 2.5 probe hygiene resolved: probes promoted to their own
    optional dep group (not polluting prod), pydantic moved to prod
    deps (it's used by Core, not just probes), `fixtures/audio_samples/`
    README documents capture protocol, uv.lock decision documented
    (commit `<HYGIENE_HASH>`)
- **Day 4 sessions** (Day 4 EOD):
  - **Session 1 — SystemClock adapter** (commit `473424c`):
    `src/integration/system_clock.py` per test_strategy §5 with
    `SYSTEM_CLOCK: Clock = SystemClock()` module-level singleton.
    Three tests: Protocol conformance via `isinstance`, monotonic
    non-decreasing, sleep elapses real wall-clock time. 19 tests
    green.
  - **Session 2 — Doc/code reconciliation** (commit `e18b595`):
    asyncio_mode drift (`pyproject.toml` "strict" vs docs "auto")
    resolved — docs updated to match code. Import path drift
    (`src.core.*` vs `core.*`) resolved — spec updated to match
    repo reality. Edits across `docs/test_strategy.md` (5 sites),
    `PROJECT_PLAN.md` (1 site), `AGENTS.md` (1 site),
    `docs/phase-5B-scaffolding.md` (7 sites). ADR-002 created.
  - **Session 3 — Phase 2.5 probe assessment** (read-only, no
    commit): full assessment of `probe_audio.py` + three Phase
    2.5 probe files under `scripts/`. Bucketed into direct-lifts
    (ffmpeg preprocessing), needs-rework (timeout via SIGALRM →
    Clock-injected asyncio.wait), and probe-only (CLI scaffolding,
    print statements). Recommended Shape B — hello-world bridge —
    for Session 4.
  - **Session 4 — Clock-wired Ollama bridge** (commit
    `<SESSION_4_HASH>`): `scripts/gemma_hello.py` ~140 lines with
    `asyncio.wait({call, timer}, FIRST_COMPLETED)` timeout race
    pattern from test_strategy §5. Two major findings:
    - **Cancellation semantics**: `asyncio.to_thread` cancellation
      is a Core-time guarantee only. Worker thread continues
      running to natural completion after `call.cancel()`; daemon
      HTTP request completes invisibly and response is discarded
      client-side. Verified via `_HangingClient` diagnostic at
      2.0s timeout — task.cancelled=True, task.done=True, thread
      still alive.
    - **Gemma 4 E2B reasoning-mode trap**: model defaults to
      `think=True`, burning 1400-1800 tokens on internal self-
      deliberation before emitting `content`. At `num_predict=400`
      the think block consumes the entire budget, leaving content
      empty or truncated. At `num_predict=1500` (Phase 2.5's value
      that "worked" for Farsi) the think block fit and content
      followed — which is why the trap stayed latent through
      100+-file testing. Solved via `ollama.chat(..., think=False)`:
      English transcription drops from 15s/400 tokens/empty
      content to 2.33s/62 tokens/valid JSON. ADR-003 records.
- **Day 5 sessions** (Day 5 EOD):
  - **Pre-flight — structlog dep** (commit `403898e`): added
    `structlog==25.5.0` to prod deps in `pyproject.toml` per
    PROJECT_PLAN §7 Locked. `uv sync` regenerated `uv.lock`.
    19 tests still green.
  - **Session 1A — OllamaAdapter skeleton** (commit `e1baa9d`):
    canonical `src/integration/ollama_adapter.py` with class shape,
    Clock-injected timeout race, `think=False` hardcoded, ffmpeg
    `_preprocess()` lifted with `PaddingUnavailable` /
    `PaddingFailed` branches, structlog event call sites,
    `TranscriptionResult` Pydantic model in `src/core/rfl_schema.py`,
    `docs/ADR/003-gemma-think-false.md`. Day-1 anchor test landed:
    `tests/integration/test_ollama_adapter_timeout.py` uses FakeClock
    for sub-millisecond deterministic timeout verification. 6
    exception classes total (1 base + 5 concrete). 20 tests green.
    The §5 spec example's single `sleep(0)` pattern was found
    insufficient for sync-client adapters — fix landed in test with
    comment; spec drift flagged for follow-up.
  - **Session 1B — adapter behavior layer** (commit `e3093bc`):
    three new tests covering 3 untested exception branches end-to-
    end: `test_padding_unavailable_when_ffmpeg_missing`,
    `test_padding_failed_on_invalid_audio`,
    `test_invalid_tool_call_on_malformed_json` (parametrized: raw
    garbage + fence-wrapped malformed). Adapter changes:
    `_strip_json_fences()` helper for Gemma's markdown-wrapped JSON
    output; structlog event payloads now match documented schema
    (`audio_path`, `model` base + per-event fields per
    test_strategy §2); validation flow strips fences before
    `TranscriptionResult.model_validate_json` and logs pre-strip
    content on failure for diagnostics. 5 of 6 exception classes
    now have direct test coverage. 24 tests green.
  - **Day 5 close-out** (commit `4469119`): `docs/test_strategy.md`
    §5 sync-client spec drift fix (single `sleep(0)` → two cycles +
    `threading.Event`-blocked HangingClient + comment) plus three
    placeholder hash sites in PROJECT_PLAN.md filled with real
    commit hashes. Docs-only commit. 24 tests still green.
  - **Day 5 EOD update** (commit `0087de1`): PROJECT_PLAN.md update
    capturing Day 5's three sessions + close-out. 211 insertions /
    148 deletions.
- **Day 6 sessions** (Day 6 EOD):
  - **Session 1 — first-pass safety_rules** (commit `bd9e734`):
    First Core module with real logic. `src/core/safety_rules.py`
    landed `SafetyResult` Pydantic model + `classify(text, lang)`
    pure function + 9-keyword English crisis detector across self-
    harm / harm-to-others / immediate-danger categories.
    "emergency" intentionally excluded — over-triggers on
    legitimate humanitarian intake speech ("I left during the
    emergency"). Non-EN langs return `is_crisis=False` with TODO
    for Day 8 multilingual. 5000-char defensive cap on input.
    Schema diverges from test_strategy §2's representative
    example (`escalate/match_path/allow_rfl_tools` → concrete
    `is_crisis/matched_keywords/suggested_action/crisis_resources_locale`)
    documented in inline class docstring. 3 anchor tests:
    crisis-blocks-intake, normal-proceeds, case-insensitive.
    27 tests green.
  - **Session 2 — GGML retry + InferenceFailed coverage** (commit
    `5306d1d`): Closed the adapter chapter. Probe identified
    `ollama.ResponseError` + `ollama.RequestError` as the SDK's
    raised types on daemon-side and transport-level failures (both
    are plausible GGML-crash modes). Refactored
    `_call_with_timeout` to propagate raw call exceptions rather
    than pre-wrapping in `InferenceFailed`; retry policy lives at
    `transcribe()` call-site with the type-specific tuple. Two new
    structlog events: `ggml_retry_attempted`,
    `inference_failed_after_retry`. Three new tests:
    retry-succeeds-on-second-attempt, retry-failure-raises-
    InferenceFailed, retry-does-not-catch-timeout (boundary test
    against future "lazy `except Exception`" regression). All 6
    adapter exception classes now have direct test coverage.
    `InferenceFailed` docstring tightened to describe retry
    semantics and the `InferenceTimeout` boundary. 30 tests green.
  - **Session 3 — RFL schema expansion** (commit `7b0470a`):
    Expanded `src/core/rfl_schema.py` from `TranscriptionResult`-
    only to a partial RFL record. Five new models — `Name`
    (canonical + source_script Literal of latin/arabic/persian/
    cyrillic/other + transliterations list), `Age` (value + Literal
    confidence flag), `LastSeen` (location + date_text both free-
    text strings), `Guardian` (present + consent flat audit
    fields, no validators per Q3 lock), `RFLRecord` (all sub-
    models optional for multi-turn intake). Field-level docstrings
    on every field of every model — load-bearing for Day 7+
    intake logic and Day 9-12 matching reading them as the spec.
    `TranscriptionResult` intentionally NOT folded into
    `RFLRecord`: two domains, two models, separated by a section-
    divider comment. Three structural tests: full-payload round-
    trip, partial-intake-validates, source_script Literal
    enforcement. 33 tests green.
- **Day 7 sessions** (Day 7 EOD):
  - **Session 1 — Spanish language routing** (commit `1ddf88c`):
    Opened multi-language work per Boss-mode locks: Q1 Spanish-
    solo first, Q2 caller passes lang, Q3 single prompt template
    with language hint, Q4 stub tests this session, Q5 multilingual
    safety as a separate session. Created
    `src/core/language_matrix.py` with `SupportedLang` Literal
    (en/es/ar/fa per §7 lock), `LANGUAGE_NAMES` dict for prompt
    construction, `IMPLEMENTED_LANGS` frozenset (en + es), and
    `is_implemented(lang)` helper. Pure Core: typing-only imports.
    Adapter signature changed to
    `transcribe(audio_path, lang: str = "en")`. New
    `UnsupportedLanguage` exception fires before any preprocessing
    when caller asks for a lang in `SupportedLang` but not in
    `IMPLEMENTED_LANGS`. Module-level `PROMPT` constant replaced
    with `_build_prompt(lang)` function interpolating
    `LANGUAGE_NAMES[lang]` via `cast(SupportedLang, lang)` at call
    site. Structlog base payload includes `lang` on every event;
    new `unsupported_language` warning event. 5 new tests (3
    adapter-level: Spanish routes, "ar" raises, English default
    unchanged regression guard; 2 matrix-level:
    `IMPLEMENTED_LANGS == {en,es}` regression guard,
    `is_implemented` membership correctness). 38 tests green.
  - **Session 2 — Arabic + Farsi language routing** (commit
    `8fa3715`): Mechanical extension of Session 1. One-line
    production change: broadened `IMPLEMENTED_LANGS` from
    `{"en", "es"}` to `{"en", "es", "ar", "fa"}`. Adapter required
    zero changes — `_build_prompt(lang)` already routed all four
    languages via `LANGUAGE_NAMES[lang]`. Stale module docstring
    + comment in `language_matrix.py` updated to reflect both
    sessions. Test changes: matrix tests' assertions broadened
    to `{en,es,ar,fa}` and `is_implemented` ar/fa booleans flipped
    to True; `test_unsupported_language_raises_before_inference`
    renamed to `test_invalid_language_raises_before_inference`
    using `lang="klingon"` (after this session "ar" is implemented;
    the regression guard now exercises non-`SupportedLang` values
    instead of unimplemented-but-supported ones — same raise
    mechanism); two new tests mirror the Spanish pattern for
    Arabic and Farsi. Farsi test asserts substring `"Persian"`
    (leading word of `LANGUAGE_NAMES["fa"]` = "Persian (Farsi)")
    so the test survives if the parenthetical is ever dropped.
    40 tests green. Routing layer COMPLETE — all four §7-Locked
    languages route through the adapter with language-aware
    prompts. NOT yet validated against real audio.

### Locked (not revisited without explicit Boss-mode decision)

- Framing: aid-worker copilot for intake, feeds Primero/proGres
- Model: Gemma 4 E2B
- Languages: EN / ES / AR / FA
- Architecture: hexagonal, three layers, enforced by test (layer
  boundary test ✅ Day 3)
- Adapter timeout: 25 seconds
- Match beat: Y-shape anchored to match card, no pill
- Submit date: May 17, 2026 (Day 24)
- Demo video target length: 2:20 (±10s)
- Block B.5 organization: per-primitive files + barrel, shared
  types in `src/ui/web/src/lib/types.ts`, component prop types
  colocated
- Python packaging: uv for env + lock, setuptools as build backend,
  ruff for linting, src/ layout with `pyproject.toml` at repo root
  (locked Day 3)
- Python dependency groups: prod (pydantic, structlog,
  future adapter deps), dev (ruff, pytest + asyncio + coverage),
  probes (isolated group for Phase 2.5 exploratory scripts)
- pydantic is a **production** dependency, not dev-only — Core uses
  it for RFL schema validation (locked Day 3; emerged from probe
  hygiene audit)
- uv.lock decision documented  _(tighten this line if you want to be
  specific about committed vs gitignored)_
- Gemma 4 E2B reasoning mode: `think=False` on every `ollama.chat`
  call (locked Day 4 Session 4; canonical adapter enforces this
  hardcoded as of Day 5 Session 1A `e1baa9d`; ADR-003 records.
  Without this, model burns 1400-1800 tokens on internal self-
  deliberation before emitting any content. With `think=False`,
  English transcription is 2.33s / 62 tokens / valid JSON.)
- structlog `25.5.0` in prod deps (locked Day 5 pre-flight `403898e`).
  Adapter uses `structlog.get_logger(__name__)` at module top.
  Event payload schema documented per test_strategy §2; refined
  Day 5 Session 1B.
- Adapter exception count: 6 classes total (1 base `AdapterError` +
  5 concrete: `PaddingUnavailable`, `PaddingFailed`,
  `InferenceTimeout`, `InvalidToolCall`, `InferenceFailed`).
  Padding-applied / padding-skipped are structlog events, NOT
  exception subclasses. (Locked Day 5 Session 1A; corrects the
  brief's earlier "seven exception classes" overcount.)
- Ollama daemon version: 0.21.0 confirmed working. Python SDK
  `ollama==0.6.1` is a distinct semver track from the daemon
  and is NOT the `≥0.20.3` version reference elsewhere in this
  document — those references are to the daemon. (Locked Day 4
  Session 4; correction to earlier ambiguity.)
- `asyncio.to_thread` cancellation is a Core-time guarantee only.
  Canonical adapter's 25s timeout bounds Core latency, not daemon
  computation. (Locked Day 4 Session 4; documented in
  `scripts/gemma_hello.py` docstring.)
- GGML retry catch-tuple: `(ollama.ResponseError, ollama.RequestError)`.
  Both are plausible GGML-crash modes (ResponseError = daemon
  caught the crash and returned HTTP 500; RequestError = daemon
  died mid-request, SDK got connection reset/EOF). Retry once,
  then surface as `InferenceFailed`. `InferenceTimeout` is NOT
  in the tuple — timeouts propagate without retry. (Locked Day 6
  Session 2 `5306d1d`.)
- `safety_rules.SafetyResult` schema: `is_crisis` + `matched_keywords`
  + `suggested_action` (Literal block_intake/proceed) +
  `crisis_resources_locale`. Diverges from test_strategy §2's
  representative example shape; may grow a `match_path` field
  when semantic detection lands Day 8-9. Concrete-shape choice
  documented in inline class docstring. (Locked Day 6 Session 1
  `bd9e734`.)
- RFL schema versioning: single growing `RFLRecord` model, no
  formal versioning. If breaking changes ever needed, they break
  inline. Hackathon scope; KIN has one consumer. (Locked Day 6
  Session 3 `7b0470a`.)
- `RFLRecord` shape decisions: `Name { canonical, source_script,
  transliterations }` (Q1 single canonical + variants list). `Age
  { value, confidence }` (Q2 single int + Literal confidence
  flag). `Guardian { present, consent }` flat audit fields, no
  cross-field validators (Q3 minor-detection enforcement deferred
  to Day 8-9 safety expansion). `LastSeen { location, date_text }`
  flat free-text strings, no date parsing (Q4 — refugees report
  partial/relative dates; matching does best-effort parsing
  later). All sub-models optional at top level for multi-turn
  intake support. (Locked Day 6 Session 3.)
- Multi-language routing: caller passes `lang: str = "en"`; no
  detection. Single prompt template parameterized by
  `LANGUAGE_NAMES[lang]`; per-language prompt files deferred to
  Day 11+ if probe data warrants. `IMPLEMENTED_LANGS` frozenset
  in `src/core/language_matrix.py` is the gate; values outside
  it raise `UnsupportedLanguage` before any inference attempt.
  (Locked Day 7 Session 1 `1ddf88c`; full set en/es/ar/fa landed
  Session 2 `8fa3715`.)
- Adapter exception count revised: 6 classes. `AdapterError` base
  + 6 concrete (`PaddingUnavailable`, `PaddingFailed`,
  `InferenceTimeout`, `InvalidToolCall`, `InferenceFailed`,
  `UnsupportedLanguage`). The Day 5 lock said "5 concrete";
  Session 1 of Day 7 added the 6th. (Updated Day 7 Session 1.)

### Open (active decisions)

- **25% checkpoint reflection (Day 8 opener — DUE).** Per §4 arc,
  Day 7-8 boundary is the 25% checkpoint. Boss-mode questions to
  answer at session opening: "Am I building the demo or adding
  features? What should I cut for the remaining 18 days? Is the
  multilingual claim load-bearing for the demo, or can I narrow
  to EN + one other if probe data is bad?"
- **Real-audio probe results (Day 8 outcome).** Today's routing
  layer is empirically untested for non-English. Day 8 probe
  determines whether: (a) all four languages produce clean
  transcription at `think=False` / `num_predict=400` (the
  optimistic path — ship as-is); (b) one or more languages
  need prompt tuning (Day 11+ per-language prompt files); (c) a
  language is broken enough to warrant cutting from the demo
  story. The demo story flexes around what the probe shows.
- **Multilingual safety_rules keyword sources.** Day 8 Session 2
  Boss-mode question: which humanitarian agencies have published
  vetted crisis keyword lists for ES/AR/FA, and how to handle
  Latin-script `.lower()` semantics for non-Latin languages
  (Arabic/Persian have no concept of case; substring match still
  works but `.lower()` is a no-op).
- Whether to use mic+waveform UI animation or skip and use static
  demo data (depends on Day 8+ end-to-end behavior; deferred to
  Day 10+ when first end-to-end intake runs)
- Canonical prompt location: `src/core/prompts.py` vs
  `tests/fixtures/gemma/prompts/intake_v1.txt`. Day 7 work
  parameterized the prompt as `_build_prompt(lang)` inside the
  adapter; `src/core/prompts.py` was NOT created. If/when fixture
  capture starts (Day 8+), the prompt-builder output may get
  written to `tests/fixtures/gemma/prompts/intake_v1.txt` for
  hash-binding. Defer the explicit Core module unless Day 9+
  matching needs to read prompts from Core.
- `num_predict` value for the canonical adapter: currently 400.
  Day 8 probe data may surface a need to vary by language;
  defer until then.
- Machine-state hygiene for demo recording day: Day 4 diagnostic
  observed 92% swap usage and Metal buffer errors during high-load
  conditions. Not affecting inference output, but track as Day 13+
  demo-hygiene item.
- Phase 2.5 probe files: keep all four as-is, collapse, or archive?
  My lean: keep but specifically prune `run_three_tests.py` (out-
  of-scope languages). Defer to Day 9+.
- Fixture capture timing: routing layer has stabilized; Day 8
  probe data is the natural moment to capture the first `*.gemma.jsonl`
  fixtures. If probe shows clean output, capture immediately. If
  probe shows broken output, defer until prompt iteration
  resolves it.
- GGML retry test design: forcing a SIGABRT in pytest is non-
  trivial. Day 6 Session 2 picked Q1 option (b) monkeypatch the
  SDK; landed clean. RESOLVED.
- test_strategy.md §5 example pattern drift: spec text was wrong
  (single `sleep(0)` insufficient for sync-client adapters). Day 5
  close-out commit `4469119` reconciled. RESOLVED.

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
- **One file per session** for Block B-class tasks. Files with
  import dependencies run sequentially, not concurrently. B.5
  Session 2 relaxed this for the type-extraction — it edited 6
  files because type moves require importer updates — but scope
  was still one logical operation ("extract shared types").
- **Stop and flag beats silently fix downstream.** If a session's
  work surfaces issues in other files, it reports rather than
  spreading the edit.
- **Propagating strictness is healthy.** When one file becomes
  stricter and creates errors elsewhere, commit the win; let the
  next file resolve the new errors.

### Git discipline

- Commits are local by default.
- `git push` requires explicit "push it" instruction from user.
- Squash + push at natural save points (end of Block B, etc.).
- Commit messages follow Conventional Commits where meaningful
  (`fix(ui):`, `refactor(ui):`, `feat(core):`, `docs:`, etc.).

### Decision hierarchy

1. User (Mark) — final authority on all decisions, especially
   framing, scope, and stop points
2. Strategy copilot (whichever Claude thread is active) — audits
   plans, flags risks, tracks governance, proposes options with
   tradeoffs
3. Claude Code sessions — execute approved plans, stop and flag
   on ambiguity, never push without explicit instruction

### Checkpoints (Boss-mode mandatory)

- **25% checkpoint (Day 7-8):** Is the agent working end-to-end? If
  not, simplify architecture tier immediately.
- **50% checkpoint (Day 15-16):** Submittable video exists? What
  should I cut for the remaining 50%?
- **75% checkpoint (Day 22-23):** LLM-judge score improved?
  Competitive differentiators emphasized?

### Iteration caps

- Visual / polish iterations: **2-3 rounds then punt.** If round 3
  isn't clearly better than round 1, move on. The match-beat icon
  went 3 rounds before landing on "no icon, Y-shape only." That was
  at the cap.
- Plan revisions: **2 rounds.** If a plan is still wrong on round 3,
  scope is probably miscalibrated, not the plan.
- Debug loops: **2 hours max without a stop-and-reflect.** If a bug
  eats 2 hours, that's a Boss-mode moment: is this still the right
  problem to solve?

---

## 9. Risks and failure modes (project-level)

See area charters (section 6) for area-specific risks. This section
tracks project-level failure modes that span multiple areas.

### Known failure modes (already defended)

- **Ollama ≤0.20.2 GGML crashes** — resolved by version pin ≥0.20.3
- **Audio head-silence padding** — canonical adapter via ffmpeg
- **25-second runaway loop** — adapter timeout, enforced by test
- **39-minute degenerate Swahili repetition** — ruled out Swahili;
  defended by timeout
- **Transliteration variance breaking matching** — solved by
  source-script preservation + fuzzy matching
- **Crisis message handled as intake** — solved by crisis detection
  blocking RFL tool calls
- **Gemma 4 E2B reasoning-mode trap** — Day 4 Session 4 discovery.
  Default `think=True` burns 1400-1800 tokens before content emits.
  Solved by `think=False` on every adapter call. Provenance:
  `scripts/gemma_hello.py` docstring + ADR-003.
- **`asyncio.to_thread` cancellation scope** — Day 4 Session 4
  characterized. Core-time-only guarantee, not daemon-time. Adapter
  design accepts this rather than fighting it.

### Risks to watch

- **Scope creep after Day 10.** Mitigation: feature freeze is a hard
  rule; "just one more thing" is the enemy.
- **Tiredness-driven architectural changes.** Mitigation: no
  all-nighters, Boss-mode checkpoints, this document as reference
  when mid-build confusion hits.
- **Claude Code session context drift on long sessions.** Mitigation:
  fresh session per task; this document as fresh-session reading
  material.
- **Devpost writeup written last-minute.** Mitigation: LLM-as-judge
  Pass 1 on Day 9 forces writeup to exist early.
- **lib/types.ts and Core Pydantic schemas drifting apart.**
  Mitigation: integration-layer adapter when Core schemas solidify
  (Day 5-7); header comment in lib/types.ts flags the relationship.
- **Machine memory pressure during demo recording.** Day 4
  observed 92% swap usage after 4 sessions + browsers + IDE.
  Mitigation: Day 13+ demo-hygiene checklist (restart, close
  browsers, quit Electron apps, clean daemon restart) before
  recording takes. Not affecting inference today but would
  corrupt demo day if ignored.
- **Provenance discipline on "Phase 2.5 validated X" claims.**
  Day 4's `num_predict=1500 "confirmed stable across EN/ES/AR/FA"`
  turned out to be Farsi-only. Other Phase 2.5 claims (Swahili
  runaway, `num_ctx=8000`, `temperature=0.1`, ffmpeg filter) have
  not been re-verified against the actual probe outputs.
  Mitigation: 20-minute Day 5 audit pass on remaining claims
  against `results/phase_2_5_final/*` before baking them into
  the canonical adapter.

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

Projected: ~55 Claude Code sessions over 25 days
Used as of Day 7 EOD: ~29-31 sessions (~53-56%)
**Ahead of pace.** Days 6 and 7 closed under-budget against
original projections, with five clean atomic commits (`bd9e734`,
`5306d1d`, `7b0470a`, `1ddf88c`, `8fa3715`). All sessions
plan-approve-execute shape with zero rework cycles.

Day 7 consumed 2 Claude Code sessions: Spanish routing (Session 1
`1ddf88c`, ~50 min) and Arabic + Farsi routing (Session 2 `8fa3715`,
~30 min). Total Day 7 Claude Code time ~80 min. Boss-mode locks
on five questions before Session 1 brief; mechanical extension
pattern in Session 2 since Session 1 nailed the routing primitive.

Day 6 consumed 3 Claude Code sessions in ~50 minutes total real
time: safety_rules first-pass (`bd9e734`), GGML retry decorator
+ `InferenceFailed` coverage (`5306d1d`), RFL schema expansion
(`7b0470a`). All three first-attempt-clean, no rework. Day 6 was
the most productive single calendar day on the project so far —
the equivalent of two normal days of work.

Day 5 consumed 3 Claude Code sessions plus a docs close-out
commit (`4469119`) and EOD update (`0087de1`). All plan-approve-
execute shape with one in-flight adjustment in Session 1B
(predictable signature-change ripple to Session 1A's timeout test
mock — fixed in-place, not regression). Day 5 closed slightly
under-budget vs original projection.

Day 4 consumed 4 Claude Code sessions plus diagnostic passes that
burned most of that strategy-copilot thread. Three of the four
were plan-approve-execute with no rework; Session 4 required a
diagnostic loop after discovering the reasoning-mode trap — the
loop was correct (surfaced a latent project-killer), not wasted.

Day 3 consumed 3 Claude Code sessions; Day 2 consumed 2; Days 0-1
are planning + UI work that predates the Python work. All plan-
approve-execute, no rework cycles.

High-velocity phase has continued through Day 7 against well-
specified targets. Day 4's reasoning-mode discovery front-loaded
the "Gemma reality checks" risk; Day 8's manual probe is the next
empirical reality check, and the first one with multilingual scope.
If the probe surfaces broken AR/FA behavior, that's where velocity
could drop. Plan Day 8 with a debug budget.

Sessions worth budgeting heavier than originally projected:
- Day 8 multilingual safety_rules: depends on Boss-mode keyword-
  source decision; could be 1-2 sessions
- Day 9-10 FastAPI + SSE routes: 2-3 sessions; this is when the
  pieces start composing into a callable system
- Days 10-12 matching logic with corroborating fields: 4-5
  sessions likely (Jaro-Winkler + multi-field scoring)
- Day 22 final video recording: 3-4 takes + editing is 6+ hours
  of human time, not session time

Sessions ahead-of-budget:
- Day 6: projected 2-3 sessions, used 3 in 50 minutes total
- Day 7: projected 2-3 sessions for routing, used 2 in 80 minutes
- The bank of saved time should NOT be spent on scope expansion;
  it's safety-margin for the empirical-reality work in Days 8-12.

---

## 11. Reference map

Files in this repo that this plan assumes you have:

- `CLAUDE.md` — product spec, coding principles, scope exclusions
- `AGENTS.md` — Claude Code operating conventions
- `docs/test_strategy.md` — authoritative test strategy
- `docs/phase-5B-scaffolding.md` — directory tree and migration spec
- `docs/ADR/001-web-ui-primary-demo-surface.md` — locked decision
  on UI as primary demo surface
- `docs/matching.md` — due before Day 6

Files in the project folder (skill outputs from planning phases):

- `/mnt/project/phase-1-problem.md` through `phase-5_7-demo-script.md`
- `/mnt/project/schedule-30day.md` — canonical 25-day schedule
- `/mnt/project/patterns.md` — what wins, what loses
- `/mnt/project/SKILL.md` — hackathon-recon skill itself

Key commits:
- `acb60d6` — Block B.5 Session 1: primitives directory split
- (Day 2 EOD) — Block B.5 Session 2: lib/types.ts extraction
- `87454cc` — Day 3 Session 1: Python scaffolding (pyproject, src
  layout, smoke test)
- `71919d9` — Day 3 Session 2: Clock Protocol + FakeClock + layer
  boundary test (16 tests passing, 0.02s)
- `<HYGIENE_HASH>` — Day 3 Session 3: probes dep group + pydantic
  promotion + audio_samples README + uv.lock decision
- `473424c` — Day 4 Session 1: SystemClock adapter per test_strategy §5
  (19 tests passing)
- `e18b595` — Day 4 Session 2: reconcile test_strategy §5/§6 drift
  with repo reality (asyncio_mode + import path; ADR-002)
- `6a45326` — Day 4 Session 4: clock-wired Ollama bridge with
  cancellation race + happy path
- `12b38d5` — Day 4 close-out: bridge findings (cancellation
  semantics + reasoning-mode trap) documented in
  `scripts/gemma_hello.py` docstring
- `403898e` — Day 5 pre-flight: structlog added to prod deps
  (PROJECT_PLAN §7 lock)
- `e1baa9d` — Day 5 Session 1A: OllamaAdapter skeleton with
  `think=False` and 25s timeout race; ADR-003 records the
  reasoning-mode decision (20 tests passing)
- `e3093bc` — Day 5 Session 1B: adapter behavior layer with padding
  tests + `_strip_json_fences()` + structlog payload schema +
  validation against malformed JSON (24 tests passing)
- `4469119` — Day 5 close-out: `test_strategy.md §5` sync-client
  spec drift fix + 3 PROJECT_PLAN placeholder hashes filled
  (24 tests passing)
- `0087de1` — Day 5 EOD: PROJECT_PLAN.md update through Sessions
  1A + 1B + close-out
- `bd9e734` — Day 6 Session 1: first-pass `safety_rules` with
  English crisis keyword detection (27 tests passing); first
  Core module with real logic
- `5306d1d` — Day 6 Session 2: GGML retry decorator on the
  adapter + `InferenceFailed` direct test coverage; closes the
  adapter exception chapter (30 tests passing)
- `7b0470a` — Day 6 Session 3: RFL schema expansion with five
  new Pydantic models (Name, Age, LastSeen, Guardian, RFLRecord)
  and field-level docstrings (33 tests passing)
- `1ddf88c` — Day 7 Session 1: Spanish language routing +
  `language_matrix.py` + adapter `lang` parameter +
  `UnsupportedLanguage` exception + `_build_prompt(lang)`
  (38 tests passing)
- `8fa3715` — Day 7 Session 2: Arabic + Farsi language routing;
  one-line broadening of `IMPLEMENTED_LANGS` to cover all four
  §7-Locked languages (40 tests passing); routing layer COMPLETE

---

## 12. Update discipline

This file is a living document. Update it:

- At the end of each phase (Phase 3 done, Phase 4 done, etc.)
- At each checkpoint (25%, 50%, 75%)
- When a locked decision changes (rare — requires Boss-mode reason)
- When a risk materializes or a new one surfaces
- When an area charter's "Definition of done" becomes met
- When the "Done" / "Locked" / "Open" sections would otherwise become
  stale

If this file and reality diverge, reality wins. Update same-day.

Last updated: April 28, 2026 (Day 7 of 25) — end of Day 7
foundation phase complete. Five commits across Days 6-7 banking
the Core layer + adapter chapter close + multilingual routing:
`bd9e734` (safety_rules first-pass), `5306d1d` (GGML retry +
InferenceFailed), `7b0470a` (RFL schema expansion), `1ddf88c`
(Spanish routing + language_matrix), `8fa3715` (AR+FA routing).
40 tests green; 6 of 6 adapter exception classes have direct
coverage; all four §7-Locked languages route through the adapter
with language-aware prompts. Day 8 opens against a fully-tested
wiring layer with the manual probe (real-audio validation across
en/es/ar/fa) as the empirical reality check, then multilingual
safety_rules expansion. 25% checkpoint reflection due at Day 8
opener per §4 arc.