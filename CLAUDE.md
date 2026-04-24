# CLAUDE.md — KIN Development Guide

> **Every Claude Code session must read this file before writing code.**
> If a request conflicts with anything in this file, STOP and flag the
> conflict. Do not silently override.
>
> For the reasoning behind the constraints in this file — what evidence
> locked which decision on what date — see `decisions.md`.

## Project: KIN
## Hackathon: Gemma 4 Good Hackathon (Kaggle) | Deadline: May 18, 2026
## Current phase: Architecture lock (Phase 4) + Web UI ADR (April 23 PM)

## One-sentence description
KIN is an offline multilingual family-reunification agent that turns a
displaced person's voice note into a structured humanitarian record —
running entirely on a single laptop via Ollama, in 4 confirmed
languages (English, Spanish, Arabic, Farsi), without a single byte of
user data leaving the device.

---

## The winning framing (do not dilute)
- **Primary prize target:** Impact Track — Digital Equity & Inclusivity ($10K)
- **Secondary:** Main Track + Global Resilience + Ollama Special Tech
- **Narrator framing (for writeup + video):** "I'm a Principal PM at
  Twilio. I ship the messaging and voice APIs humanitarian tools
  depend on. I see the support tickets when those networks fail."
- **Hero of the demo:** the displaced parent. NOT the narrator.
- **What KIN IS:** a data-structuring tool for aid workers and
  displaced people.
- **What KIN IS NOT:** a caseworker substitute, a clinician, a
  therapist, an official ICRC integration.

## Confirmed demo languages
KIN demos in exactly 4 languages: **English, Spanish, Arabic, Farsi.**
Do not test, add, or reference other languages in implementation.
French, Portuguese, Bengali, Ukrainian, Swahili, Tigrinya, and Amharic
were evaluated during Phase 2.5 and ruled out. See `decisions.md`
for sweep results.

**Crisis coverage by language:**
- Arabic → Syrian, Iraqi, Yemeni, Sudanese, Palestinian displacement
- Spanish → Venezuelan, Central American, Colombian displacement
- Farsi → Afghan and Iranian displacement (incl. Dari-speaking diaspora)
- English → caseworker-facing + anglophone resettlement countries

## Headline stats (verified, usable in writeup + video)
- ICRC Trace the Face: **4.1% reunification rate** (309 of 7,490 photos)
- **117.3M** people forcibly displaced globally (UNHCR)
- **49M** of those are children
- Phase 2.5 evidence: **32 probes across 9 candidate languages, 4 confirmed**

---

## Model choice — Gemma 4 E2B
KIN runs on Gemma 4 E2B. Do not substitute E4B, 26B, or 31B.

KIN's pitch rests on running on the hardware field workers,
caseworkers, and displaced people actually have — a 5-to-10-year-old
laptop, typically 8-16 GiB of RAM, no dedicated GPU. E2B (~2.3B
effective parameters, ~3-5 GiB resident at Q4) fits that profile. E4B
(~4.5B effective, ~7-9 GiB resident) requires more memory than many
field-deployed laptops have available after the OS and a browser.

### Writeup-ready paragraph (verbatim OK to use)
> KIN runs on Gemma 4 E2B — the smallest Gemma 4 variant, roughly
> 2 billion effective parameters. We deliberately chose E2B over the
> larger E4B because KIN's value depends on running on the hardware
> that field workers, caseworkers, and displaced people actually have
> access to — typically a 5-to-10-year-old laptop with 8-16 GiB of
> RAM, not a workstation. E4B is a better model in absolute terms.
> E2B is the better model for KIN.

## Hardware target
The demo is recorded and benchmarks are run on a **MacBook Air M4,
16 GiB unified memory, 256 GiB SSD**. The target persona's actual
hardware is likely worse.

Do NOT assume the demo machine has headroom for:
- Multiple models loaded concurrently (Ollama default is one at a time)
- Massive context windows (keep system prompts under 2K tokens)
- Long background processes during demo recording (close browsers,
  Docker, Slack, heavy IDEs before recording)

---

## Judges we optimize for (priority order)
1. **Glenn Cameron** — strongest advocate; rewards humanitarian +
   multilingual + offline narratives.
2. **Median-judge cluster** (Martins, Sanseviero, Ballantyne,
   Warkentin, Lacombe) — rewards offline Gemma + native tool calling +
   ecosystem tooling.
3. **Dr. Megan Jones Bell** — one potential blocker; pre-empt safety
   concerns explicitly in writeup + video.
4. **María Cruz** — rewards reproducibility, non-English reach, open eval.

---

## Architecture
**Pattern:** Hexagonal (ports + adapters) with a strict three-layer model.

```
┌──────────────────────────────────────────────────────────────┐
│  PLATFORM/UI LAYER                                           │
│  - Web UI (React + Tailwind + shadcn/ui) — PRIMARY intake    │
│    surface, recorded in demo video                           │
│  - FastAPI server (127.0.0.1 only) wrapping ollama_adapter   │
│  - Terminal UI for dev, tests, debugging                     │
│  - Claude Code via Ollama Anthropic-compat (caseworker side) │
│  - NEVER contains business logic                             │
└─────────────────┬────────────────────────────────────────────┘
                  │
┌─────────────────▼────────────────────────────────────────────┐
│  INTEGRATION LAYER (adapters only)                           │
│  - ollama_adapter.py  → wraps Ollama SDK, owns canonical     │
│                         padding + timeout + logging          │
│  - storage_adapter.py → local JSON queue (no network)        │
│  - sync_adapter.py    → mocked ICRC/REFUNITE queue (no real  │
│                         API call — we produce NGO-ready JSON)│
│  - ZERO business logic                                       │
└─────────────────┬────────────────────────────────────────────┘
                  │
┌─────────────────▼────────────────────────────────────────────┐
│  CORE LAYER (pure logic, no I/O)                             │
│  - rfl_schema.py      → RFL field definitions + validators   │
│  - safety_rules.py    → trauma-informed refusals + escalation│
│  - scoring.py         → confidence scoring for tool calls    │
│  - language_matrix.py → which languages are supported        │
│  - FULLY TESTABLE with no network, no model, no files        │
└──────────────────────────────────────────────────────────────┘
```

**Every function belongs to exactly ONE layer.** Violations must be flagged.

## Key boundaries (non-negotiable)
- **Core layer has zero I/O.** No network, no disk, no model calls.
- **Integration layer never makes decisions.** If an adapter contains
  `if` statements about WHAT to do (not HOW to connect), it's misplaced.
- **UI layer is dumb.** Orchestration only; all decisions come from Core.
  This applies to the FastAPI server and the React app equally — no
  business logic in `src/ui/server.py` or `src/ui/web/`.
- **No cloud calls, ever.** Not OpenAI, not Anthropic cloud, not Google
  API. Ollama local only. Any commit adding a remote API client is a bug.
- **FastAPI binds to 127.0.0.1 only.** Never 0.0.0.0. No network egress
  path exists.

## Demo surface (per ADR April 23 PM)
- **Intake flow (primary recorded surface):** React web UI served by
  local FastAPI. This is what the judge sees for the Spanish fill,
  minor-detection beat, transliteration-match wow moment, and Arabic
  semantic-crisis beat.
- **Caseworker review beat:** Claude Code terminal pointed at
  `http://localhost:11434/v1` (Ollama Anthropic-compat). Unchanged.
  Intentional contrast with the web intake UI.
- **Dev/test surface:** Terminal UI (`src/ui/terminal_demo.py`).
  Not recorded. Used for development and test scaffolding.

## Web UI scope (locked — do not expand)
- Single page. No routing. No auth. No settings. No history views.
- Components: record card, waveform inset, function-call trace panel,
  completeness meter, live timer, static baseline label, colored state
  borders, persistent inline labels, transliteration-match split panel.
- State streaming via SSE from FastAPI → React. One-way.
- Hard build budget: 20 hours across Days 1–10. Cutoff Day 14.
- If tracking over 25 hours, revert to terminal demo surface.

## Agent design principles
1. **One agent, one job, one sentence.** KIN has ONE agent. Voice input
   → structured RFL record. Do not propose multi-agent orchestration.
2. **Every LLM output is validated against a Pydantic schema** before
   it's trusted.
3. **Every tool call gets a deterministic fallback.** Invalid JSON →
   Core validator rejects → "ask for clarification" response.
4. **Constraints at the tool level, not the prompt level.** Enforce
   required fields in Pydantic, not the system prompt.
5. **Every action is logged to a local audit trail.** Judges may
   review this log; treat it as demo surface.
6. **"NEVER do X" prompts work better than "try to avoid X".**
7. **Reasoning mode is visible.** `<|think|>` traces are a demo feature,
   not a side effect.

---

## Gemma 4 capabilities we rely on (load-bearing)
All four confirmed during Phase 2.5:
1. **Audio input on E2B** — ≤30s clips, confirmed for 4 languages.
2. **Native function calling** — `<|tool_call|>` tokens via Ollama.
3. **Reasoning mode** — `<|think|>` for ambiguity resolution.
4. **Offline execution via Ollama on M-series Mac** — fundamental.

## Learned audio pipeline constraints
Five operating rules derived from Phase 2.5. Treat as locked.

1. **Head-silence padding is mandatory preprocessing.**
   Apply `ffmpeg -af "adelay=1000|1000,apad=pad_dur=0.5"` to every
   audio input before inference. Unpadded audio drops the first
   ~1-2 seconds ~40% of the time on gemma4:e2b. Lives in the
   Integration layer as canonical pre-inference — NOT a per-call option.

2. **Gemma 3n E2B is not a fallback for audio.**
   Through the Ollama Python SDK audio path, gemma3n:e2b fabricates
   responses entirely. Do not use it as backup. Do not retest.

3. **Warm-model inference budget: 7-17s on 10-15s clips at temp=0.1.**
   Hard ceiling 25s per inference. The 30s end-to-end budget cannot
   accommodate two sequential inferences per turn. Design for
   single-shot reasoning + tool call. Multi-turn clarification is a
   separate user interaction, not a chained inference.

4. **Low-confidence audio → runaway generation loops.**
   When the audio encoder produces low-confidence features, Gemma 4
   E2B can enter decoder loops without hitting EOS (observed: 39
   minutes of degenerate repetition on a single Swahili clip). Any
   production path MUST enforce a hard timeout per inference (25s
   Integration layer, 30s probe). Without this, a single bad input
   hangs the pipeline.

5. **English-output framing does not unlock additional languages.**
   The encoder is the bottleneck at input and cannot be sidestepped
   by decoder-side prompt shaping. Do not propose "translate-only"
   variants for the failed languages.

---

## Ollama quirks & known issues
- **Audio is passed via the `images` field.** Python SDK has no
  `audio` parameter; server routes based on model + blob content.
  Encode WAV as base64 in `images=[...]`.
- **Gemma 4 + audio on Ollama ≤0.20.2** has an intermittent GGML
  assertion crash every 2-5 sustained audio requests. Dev env is on
  0.21.0 and saw zero crashes across 32 Phase 2.5 probes. Upgrade past
  0.20.2 if deploying elsewhere.
- **Flash Attention bug on long prompts (>3K tokens)** hangs Gemma
  dense models on Ollama 0.20.2. Keep system prompts under 2K tokens
  regardless.
- **`ollama search` does NOT exist as a CLI subcommand.** Use
  `curl https://registry.ollama.ai/v2/library/gemma4/tags/list`.
- **HuggingFace datasets cache grows fast and silently.** FLEURS
  downloads double-cache (tarballs + extracted arrow files). On a
  256 GiB machine, budget disk before fetching multiple language
  datasets, or: fetch → extract WAVs to `audio_samples/` → clear
  cache → fetch next.

## Ollama features we showcase (for Ollama Special Tech prize)
It is NOT enough to "use Ollama." We must showcase Ollama-specific features:
1. **Streaming tool calls** — visible in the demo via the function-call
   trace panel in the web UI.
2. **Native `tools=[]` parameter** in the Python SDK.
3. **Anthropic API compat layer** — Claude Code on caseworker side
   points at `http://localhost:11434/v1` and reviews cases against
   Gemma 4 E2B. Non-obvious differentiator.
4. **Approval Manager / human-in-the-loop** — every tool call is
   gated by a review step before submission.

A Claude Code session that implements Gemma access WITHOUT these
features has missed the Special Tech prize angle.

---

## Code style
- **Python 3.11+** (confirmed: 3.11.15).
- **Type hints on every function.** `mypy --strict` must pass.
- **Pydantic v2 models for all data structures** that cross layers.
- **Structured logging** via `structlog` — no `print()` outside demo UI.
- **Tests mirror source:** `src/core/scoring.py` → `tests/core/test_scoring.py`.
- **No comments that restate code.** Comments explain WHY, not WHAT.
- **File headers:** first line is a one-sentence docstring describing
  the file's single responsibility.
- **Web UI:** React function components only. Tailwind utility classes.
  shadcn/ui primitives where applicable. No Redux, no external state
  libraries — component state + SSE is sufficient.

## What NOT to build (explicit scope exclusions)
A Claude Code session that implements any of these has violated
CLAUDE.md and should flag the violation, not proceed.

- ❌ **Fine-tuning.** Unsloth prize was dropped.
- ❌ **Substituting E4B, 26B, or 31B for E2B.** Model is locked.
- ❌ **Testing languages ruled out during Phase 2.5** (French,
  Portuguese, Bengali, Ukrainian, Swahili, Tigrinya, Amharic).
- ❌ **Real ICRC/REFUNITE API integration.** APIs are closed. We
  produce RFL-schema-compliant JSON payloads and nothing more.
- ❌ **Mobile app (native iOS/Android).** Demo is on a Mac.
- ❌ **Mental-health therapy features.** Route to crisis hotlines.
- ❌ **Asserting facts the user didn't state.**
- ❌ **Any cloud API call.** Ollama local only.
- ❌ **Speculative features** (photo matching, biometrics, blockchain,
  federated learning). Out of scope.
- ❌ **Multi-agent orchestration.** One agent only.
- ❌ **UIs beyond the locked single-page intake web app + terminal
  caseworker review.** No multi-screen, no auth, no history views,
  no settings panel, no records list UI, no mobile/responsive layouts
  — see ADR dated April 23 PM.
- ❌ **Web search, web scraping, RAG over the open internet.**
- ❌ **FastAPI binding beyond 127.0.0.1.** Never 0.0.0.0.
- ❌ **Business logic in `src/ui/server.py` or `src/ui/web/`.** Layer
  violation — all decisions come from Core.
- ❌ **React Clock Provider or useClock() hook.** Symmetry with the
  Python Clock port is the wrong instinct — vi.useFakeTimers is
  native Vitest and requires zero production code. See Phase 5A §5
  pushback.
- ❌ **Pre-commit running full test suite.** The tiered setup is
  non-negotiable. A slow pre-commit hook gets bypassed with
  --no-verify within 48 hours and stops mattering. Fast tier
  (Core + Integration without coverage) on pre-commit; full tier
  on pre-push.
- ❌ **Early fixture capture (before Day 5).** Prompts are still
  moving. Fixtures captured on Day 1 will be stale by Day 4 and
  the staleness check becomes a nuisance rather than a guard.
- ❌ **Automatic git push.** Never push without explicit user
  instruction. Do not write helper scripts that push. Do not
  suggest "let me push this so it's safe" — commits are the
  durability mechanism, push is the visibility mechanism, and
  visibility is the user's decision.

---

## Demo requirements (priority order)
Features that MUST work for the demo. Priority = order of protection
when scope-cutting.

1. **MUST WORK:** Audio input in English, Spanish, Arabic, Farsi **via
   web UI** → transcription + translation → Gemma 4 E2B reasoning →
   valid RFL tool call → structured JSON output. ALL OFFLINE.
2. **MUST WORK:** Visible Wi-Fi/airplane-mode indicator on screen
   during demo recording.
3. **MUST WORK:** Claude Code connected to local Ollama via Anthropic
   compat layer, reviewing a queued RFL record (caseworker beat).
4. **MUST WORK:** Safety escalation pattern — if user input mentions
   self-harm, unaccompanied minor, or crisis keywords (in ANY of the
   4 languages), KIN returns a hardcoded referral to IFRC/UNHCR/ICRC
   hotlines and does NOT call the RFL tool.
5. **MUST WORK:** Terminal dev surface remains operational for tests
   and debugging.
6. **SHOULD WORK:** Multi-turn clarification (model asks for missing
   required fields before calling tool).
7. **SHOULD WORK:** Transliteration-match beat renders split-panel +
   match card in web UI (wow moment surface).

## Multilingual safety requirement
Crisis-phrase detection must work across all 4 supported languages
(EN/ES/AR/FA), not just English. Implementation approach is open —
multilingual keyword list, translation-then-match, or model-based
classification are all options. To be decided in Phase 4.

## Writeup paragraphs needing revision in Phase 3.5
The "calibrated opening paragraph" in `phase2_research_summary.md`
still references Tigrinya/Amharic/Dari/Pashto as demonstration
languages. Rewrite in Phase 3.5 using confirmed languages (EN/ES/AR/FA)
and the populations they serve.

---

## Testing requirements

Test strategy is documented in full at `docs/test_strategy.md` (from
Phase 5A Opus pass, April 23). Summary targets below.

### Acceptance is invariant-based, not count-based
Target shape at feature freeze (Day 18):
- ~35 Core tests (95% coverage target — pure functions, no excuse)
- ~25 Integration tests (every adapter error branch has a dedicated
  test against a stub Ollama client)
- ~10 FastAPI/SSE tests (routes + SSE event types + 127.0.0.1 bind
  assertion)
- ~18 React component tests (state transitions, not pixels; Vitest
  + RTL + vi.useFakeTimers)
- 1 Playwright E2E (Spanish-fill happy path against mocked adapter)
- 10 red-team cases (see `docs/test_strategy.md` §4)

Total ~99 tests. This is the shape, not a quota. If invariants hold
with fewer, that's fine; if they need more, that's also fine.

### The invariants that must hold
1. Crisis detection blocks RFL tool calls across all 4 languages
   (keyword + semantic paths)
2. Age < 18 forces Guardian schema and routes to child-protection
3. ollama_adapter enforces 25s hard timeout via FakeClock
4. Every structured output validated against Pydantic before trusted
5. No fatal assertions about missing persons, in any language
6. No fabrication of fields the speaker didn't state
7. Prompt injection refused and logged
8. Zero network calls in any test (conftest monkeypatches
   `socket.socket` to raise)
9. Fixture prompt hashes match source; staleness fails CI loudly
10. Ollama model tag asserted as `gemma4:e2b` in CI

### The 3 tests to write FIRST (Day 1 of test phase)
1. `tests/core/test_safety_rules.py::test_crisis_blocks_rfl` —
   parametrized over 4 languages × (keyword + semantic)
2. `tests/core/test_rfl_schema.py::test_minor_forces_guardian`
3. `tests/integration/test_ollama_adapter_timeout.py::test_timeout_fires_at_25s`

### Tiered commands
- **Pre-commit** (fast, <10s): ruff + mypy Core/Integration +
  `pytest tests/core tests/integration -q -x --no-cov`
- **Pre-push** (full, <30s): `pytest -q` including red-team
- **On demand:** `pnpm vitest --run`, `pnpm exec playwright test`

### Fixtures (captured Day 5-7 when prompts stabilize, NOT Day 1)
- 20+ real Gemma 4 E2B responses in `tests/fixtures/gemma/`
- Content-addressed: every fixture binds to a prompt SHA
- `conftest.py` fails the session if any fixture's prompt has
  drifted from capture-time
- Capture session is a ~4-hour block, not incremental

### Clock port (see `docs/test_strategy.md` §5 for full code)
- **Python:** `src/core/clock.py` defines the Protocol. Real adapter
  `src/integration/system_clock.py` wraps `time.monotonic` +
  `asyncio.sleep`. `tests/fakes/fake_clock.py` is a heapq-based
  deterministic fake. Adapters receive the clock via constructor
  injection. DO NOT add a React Clock Provider — use
  `vi.useFakeTimers()`.
- **React:** `vi.useFakeTimers()` at test time. Zero production
  changes, zero DI ceremony. Hexagonal purity is a Python-side
  concern.

## Safety posture (non-negotiable, pre-empts Dr. Megan Jones Bell)
1. KIN's system prompt explicitly forbids asserting that a missing
   person is alive, dead, or located. Only relays registry responses.
2. Crisis trigger phrases in any of the 4 supported languages bypass
   the RFL flow entirely and return hardcoded hotline referrals.
3. Unaccompanied-minor flow is separate: KIN flags and routes to
   UNHCR child protection rather than attempting reunification.
4. No data leaves the device. Period. The demo must prove this.
5. User-facing scope statement: "KIN is a tool for aid workers and
   displaced people — not a replacement for caseworkers, clinicians,
   or verified registries."
6. `safety_rules.py` in Core owns all of the above. Any behavior
   change requires a change to that file, reviewed and tested.

---

## File / directory structure (target)

```
kin/
├── CLAUDE.md                 # this file
├── decisions.md              # append-only locked-decisions log
├── README.md                 # public-facing, judges will read
├── pyproject.toml
├── .env.example
├── .gitignore
├── audio_samples/            # test audio (gitignored)
├── src/
│   ├── core/                 # pure logic, no I/O
│   │   ├── rfl_schema.py
│   │   ├── safety_rules.py
│   │   ├── scoring.py
│   │   └── language_matrix.py
│   ├── integration/          # adapters only
│   │   ├── ollama_adapter.py # owns padding + timeout + logging
│   │   ├── storage_adapter.py
│   │   └── sync_adapter.py
│   └── ui/
│       ├── terminal_demo.py
│       ├── caseworker_review.py
│       ├── server.py         # FastAPI, 127.0.0.1 only
│       └── web/              # React + Tailwind + shadcn/ui
│           ├── src/
│           ├── public/
│           └── package.json
├── tests/
│   ├── core/
│   ├── integration/
│   ├── ui/                   # FastAPI + React component tests
│   ├── e2e/                  # one Playwright happy-path test
│   └── fixtures/
├── results/                  # recon outputs (gitignored raw JSONs)
│   └── phase_2_5_final/      # archived probe JSONs
├── scripts/
│   ├── probe_audio.py        # ad-hoc probe tool
│   ├── fetch_*.py
│   └── test_audio_smoke.py
└── docs/
    ├── architecture.md
    ├── safety.md
    └── demo_script.md
```

## Definition of done (final submission)
- [ ] Audio in 4 confirmed languages (EN/ES/AR/FA) transcribed
      reliably on E2B, 3 consecutive clean runs each on the 16 GiB
      M4 Air.
- [ ] Native function calling produces valid RFL records in all 4.
- [ ] Safety layer catches all 10 red-team test cases across 4
      languages.
- [ ] Web UI renders all storyboard components (record card, waveform
      inset, function-call trace, completeness meter, colored state
      borders, transliteration match split panel).
- [ ] Claude Code + Ollama Anthropic-compat caseworker review works.
- [ ] All 10 invariants from test_strategy.md §2 hold. Full test
      suite (~99 tests) green. Zero network calls (conftest socket
      monkeypatch in place). Ollama model tag CI assertion present.
- [ ] Safety section in writeup addresses Dr. Megan Jones Bell's four
      concerns explicitly.
- [ ] Video at 2:20 ± 15s; opens with human stakes; all 4
      "must-appear-by-0:60" elements in place.
- [ ] Kaggle writeup ≤1,500 words, includes Cameron-calibrated opening
      paragraph and median-judge sentence.
- [ ] Public GitHub repo, one-command Ollama setup, HF model card.
- [ ] Reproducibility: someone can clone the repo and run the demo on
      their own 16 GiB laptop in <10 minutes.

## Prompting conventions for Claude Code
- ALWAYS read this file first.
- If a request conflicts with CLAUDE.md, ask before proceeding.
- Default to the architecture and boundaries above unless told otherwise.
- Ask clarifying questions BEFORE writing code, not after.
- Show file trees and primary files BEFORE running anything.
- Never execute benchmarks yourself — those are run by the human.
- Flag new dependencies for approval.
- Commit message format: `phase-N: <what>` e.g. `phase-4: ollama adapter`.

## Git & version control conventions
- Local-only git during build. Commit freely during work sessions.
- Local identity: `mark@brazinski.us` / `Mark Brazinski` (local config,
  not global).
- **Push only when the user explicitly says "push it" (or equivalent).**
  Never push on your own initiative, never push at the end of a session,
  never push "to be safe." The user controls when work becomes visible
  on the remote.
- If the user asks to push and there are commits to push, run
  `git push` plainly. No timestamp rewriting, no force-push, no
  history rewriting unless explicitly requested.
- A session running at 14:00 that has code to share should stop at
  `git commit`. Not `git push`.

---

**Last updated:** April 23, 2026 (PM) — web UI ADR ratified