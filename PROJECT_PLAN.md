# KIN — Master Project Plan

> Living document. Commit to repo root. Update at every checkpoint and
> major decision. If this file and reality diverge, reality wins and
> this file gets updated same-day.

Last updated: April 25, 2026 (Day 4 of 25) — end of Day 4. Four
Claude Code sessions plus a diagnostic pass. SystemClock adapter
landed (`473424c`). Docs/code reconciled on asyncio_mode + import
path drift (`e18b595`). Phase 2.5 probe surface assessed. Clock-
wired Ollama bridge built, timeout cancellation semantics
characterized, Gemma 4 E2B reasoning-mode trap discovered and
solved via `think=False`. 19 tests green; adapter has known-good
2.33s English transcription path.
Maintainer: Mark Brazinski (solo developer)
Next scheduled update: end of Day 5 canonical adapter work, or
25% checkpoint (Day 7-8), whichever comes first.

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
Day  5  │   Gemma hello-world, first audio pipeline,
Day  6  │   test environment, core data model,
Day  7  │   25% checkpoint ★
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

### Day 5 scope (next session)

Canonical `src/integration/ollama_adapter.py`. This is the largest
adapter session of the project — `test_strategy.md §2` lists seven
error branches that all land here: padding applied, padding skipped,
ffmpeg missing, ffmpeg non-zero exit, 25s timeout, malformed JSON
(`InvalidToolCall`), GGML crash retry. Plus structlog on every call.
Plus the first adapter-seam tests using FakeClock for the timeout
branch specifically.

Day 4's bridge work (`scripts/gemma_hello.py`) and diagnostic passes
banked three findings that shape Day 5's design:

**1. `think=False` is non-negotiable.** Gemma 4 E2B defaults to
`think=True` and burns 1400-1800 tokens on internal self-
deliberation before emitting `content`. With `think=False`, English
transcription runs in 2.33s at 62 tokens with valid JSON in
`content` and natural-EOS stop. The canonical adapter sets this
parameter on every call. ADR-003 records the decision. The 100+-
file Phase 2.5 testing likely ran at `num_predict=1500` where the
think block happened to fit inside budget — which is why the trap
stayed latent until Day 4 ran at `num_predict=400`.

**2. `asyncio.to_thread` cancellation is a Core-time guarantee
only.** The 25s timeout fires correctly in Core's timeline when
the timer wins the race, but the worker thread wrapping
`ollama.chat` continues running to natural completion. The
underlying daemon HTTP request completes invisibly and the response
is discarded client-side. Design implication: the adapter's
timeout is a "Core returns within 25s" contract, not "daemon stops
computing within 25s." Documented in `scripts/gemma_hello.py`
docstring; Day 5's adapter inherits.

**3. Phase 2.5's canonical ffmpeg function is ready to lift.**
`scripts/test_audio_smoke.py:32-43` contains the production-ready
`preprocess(src, dst)` function with `adelay=1000|1000,apad=pad_dur=0.5`
and 16kHz mono s16 conversion. Day 5 copies verbatim into the
adapter; no re-derivation needed. The only change: replace
`subprocess.run(..., check=True)` with explicit handling that
raises `PaddingUnavailable` on `FileNotFoundError` and
`PaddingFailed` on non-zero exit — matching the §2 error-branch
names.

Target deliverables (budget: 3-4 Claude Code sessions across Days
5-6, not 1-2; §10 budget assumed 4-6 across Days 4-5 combined but
Day 4 used 4 with much of it on diagnostics rather than adapter
code, so Day 5 absorbs more adapter work than originally projected):

- `src/integration/ollama_adapter.py` — canonical adapter with all
  seven error branches, Clock-injected 25s timeout, `think=False`,
  structlog instrumentation, Pydantic validation of output
- `src/core/prompts.py` (or equivalent) — single authoritative home
  for the locked transcription prompt, replacing the four-way
  duplication across `probe_audio.py` + three Phase 2.5 probe files
- `src/core/rfl_schema.py` — first-pass Pydantic models for the
  `transcription` and `english_translation` fields the adapter
  returns (full RFL record shape matures Days 6-7)
- `tests/integration/test_ollama_adapter_timeout.py` — the Day-1
  anchor test from `test_strategy.md §8`, using FakeClock
- `docs/ADR/003-gemma-think-false.md` — records the reasoning-mode
  decision with provenance

Explicitly **not** Day 5 scope (pushed to Day 6-7):
- Retry logic on GGML crashes (adapter error branch #8 in the §2
  list — land with tests Day 6)
- Full RFL record shape (Name, Age, Relationship, LastSeen,
  Guardian, DistinguishingMarks) — transcription+translation is the
  Day 5 deliverable, richer schema is Day 6-7
- Live microphone capture (Day 7+)
- Languages beyond EN (Spanish Day 6, Arabic + Farsi Day 7-8)
- FastAPI + SSE routes (Days 9-10)

Day 5 is a Boss-mode opening. Fresh strategy-copilot session brief
before Claude Code opens. First Session 1 brief written against
this document and the `scripts/gemma_hello.py` docstring findings.

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

**Progress markers (Day 4 EOD):**
- `src/integration/system_clock.py` — ✅ done (Day 4 Session 1,
  commit `473424c`)
- `scripts/gemma_hello.py` — ✅ done (Day 4 Session 4,
  commit `<SESSION_4_HASH>`). Clock-wired Python↔Ollama bridge;
  happy path runs English transcription in 2.33s at 62 tokens
  with `think=False`. NOT the canonical adapter — scripts/
  throwaway that Day 5's `ollama_adapter.py` supersedes.
- Gemma 4 E2B runtime behavior characterized: reasoning mode is
  the default and must be disabled via `think=False`; audio
  encoder works cleanly; pre-M5 Metal buffer errors on stderr
  are benign (GGML logs them but inference succeeds).
- `asyncio.to_thread` cancellation documented as Core-time-only
  guarantee; daemon-side computation continues invisibly after
  `call.cancel()`. Canonical adapter inherits this semantic.
- Ollama daemon version 0.21.0 confirmed working; Python SDK
  `ollama==0.6.1` (distinct semver track from daemon).
- Phase 2.5 probe surface fully assessed (Session 3). Canonical
  ffmpeg filter at `scripts/test_audio_smoke.py:32-43` ready to
  lift into canonical adapter Day 5.
- Canonical `ollama_adapter.py` with all seven §2 error branches
  + Pydantic validation + structlog: starts Day 5.

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
  DistinguishingMarks  _(docstring stub as of Day 3 EOD; full shape Day 5-7)_
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
  call (locked Day 4 Session 4; ADR-003 records. Without this,
  model burns 1400-1800 tokens on internal self-deliberation
  before emitting any content. With `think=False`, English
  transcription is 2.33s / 62 tokens / valid JSON.)
- Ollama daemon version: 0.21.0 confirmed working. Python SDK
  `ollama==0.6.1` is a distinct semver track from the daemon
  and is NOT the `≥0.20.3` version reference elsewhere in this
  document — those references are to the daemon. (Locked Day 4
  Session 4; correction to earlier ambiguity.)
- `asyncio.to_thread` cancellation is a Core-time guarantee only.
  Canonical adapter's 25s timeout bounds Core latency, not daemon
  computation. (Locked Day 4 Session 4; documented in
  `scripts/gemma_hello.py` docstring.)

### Open (active decisions)

- Fixture capture timing: Day 5-7 target, exact timing depends on
  when prompts stabilize
- Whether to use mic+waveform UI animation or skip and use static
  demo data (depends on Day 5 audio pipeline behavior)
- Canonical prompt location: `src/core/prompts.py` (Core-ish,
  single authoritative home) vs `tests/fixtures/gemma/prompts/intake_v1.txt`
  (matches test_strategy §3 versioning convention). Day 5 Session 1
  picks; my lean is Core-facing module with a `PROMPT_V1` constant
  that also gets written to the fixture directory for hash-binding.
- `num_predict` value for the canonical adapter: Phase 2.5's 1500
  was validated against reasoning-mode-on (where the think block
  needed the headroom); with `think=False` locked, the real budget
  is probably 200-400 tokens. Day 5 measures empirically on each
  language and picks per-language or global, depending on spread.
- Machine-state hygiene for demo recording day: Day 4 diagnostic
  observed 92% swap usage and Metal buffer errors during high-load
  conditions. Not affecting inference output (confirmed via
  `think=False` test), but worth documenting a "before recording"
  checklist: restart laptop, close browsers, quit Electron apps,
  clean Ollama daemon restart. Track as Day 13+ demo-hygiene item.
- Phase 2.5 probe files: keep all four as-is, collapse into one
  consolidated probe, or archive + delete. My lean (from Session 3
  assessment): keep as-is but specifically prune `run_three_tests.py`
  since it targets out-of-scope languages. Defer to Day 5-6.

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
Used as of Day 4 EOD: ~21-23 sessions (~38-42%)
On pace. Day 4 consumed 4 Claude Code sessions (SystemClock, doc
reconciliation, probe assessment, clock-wired bridge) plus
diagnostic passes that burned most of this strategy-copilot thread.
Three of the four sessions were plan-approve-execute shape with no
rework; Session 4 required a diagnostic loop after discovering the
reasoning-mode trap — the loop was correct (surfaced a latent
project-killer), not wasted.

Day 3 consumed 3 Claude Code sessions (scaffolding, clock+layer-test,
probe hygiene) plus strategy-copilot plan reviews on this thread.
All three were plan-approve-execute shape, no rework cycles.

Day 2 consumed 2 Claude Code sessions (B.5.1 primitives split, B.5.2
lib/types.ts extraction) plus strategy-copilot plan reviews on this
thread. Both Claude Code sessions were one-shot plan-approve-execute,
no rework cycles.

High-velocity phase continued through Day 4 against a mix of
well-specified targets (SystemClock, doc reconciliation) and
first-contact-with-reality work (Gemma runtime behavior). Day 4's
reasoning-mode discovery front-loaded the "velocity drops when
Gemma reality checks hit" risk — it arrived on Day 4 instead of
Day 7+, which is good (found on Day 4, fixable in one parameter,
before architecture was committed). Day 5 opens against known
reality: `think=False` baseline, Clock-wired timeout pattern
proven, ffmpeg function ready to lift.

Sessions worth budgeting heavier than originally projected:
- Day 5 canonical adapter: 3-4 sessions (originally 1-2 because
  Day 4 was assumed to split the work; Day 4's diagnostic load
  shifted real adapter work to Day 5)
- Days 10-12 (matching logic with corroborating fields): 4-5
  sessions likely
- Day 22 (final video recording): 3-4 takes + editing is 6+ hours
  of human time, not session time

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
- `<SESSION_4_HASH>` — Day 4 Session 4: clock-wired Ollama bridge
  with cancellation semantics + reasoning-mode findings (ADR-003)

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

Last updated: April 25, 2026 (Day 4 of 25) — end of Day 4 foundation
phase. Commits: `473424c` (SystemClock), `e18b595` (doc
reconciliation + ADR-002), `<SESSION_4_HASH>` (clock-wired Ollama
bridge + ADR-003). Two major findings this day: `asyncio.to_thread`
cancellation is Core-time-only; Gemma 4 E2B requires `think=False`
to avoid reasoning-mode trap. Day 5 opens against known reality.