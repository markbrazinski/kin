# AGENTS.md — Claude Code Conventions for KIN

> **Purpose:** This file tells AI coding agents (primarily Claude Code) how
> to work inside the KIN repo. It complements `CLAUDE.md` (what KIN is and
> what it must do) with the operational conventions for sessions that write
> code.
>
> **Read order for a fresh session:** `CLAUDE.md` first, then this file,
> then `docs/test_strategy.md` if the task involves tests, then the specific
> file being modified.
>
> **If anything here conflicts with `CLAUDE.md`, flag the conflict. Do not
> silently resolve.**

---

## Before writing any code

Every session starts with these four checks. Skip them and you will
violate architecture, scope, or safety rules and waste the user's time.

1. **Read `CLAUDE.md`.** Non-negotiable. This is where scope exclusions,
   architecture boundaries, and safety invariants live.
2. **Confirm the task's layer.** KIN has three layers: Core (pure), 
   Integration (adapters only), UI (orchestration only). Before writing
   any function, state out loud which layer it belongs to. If you can't
   decide, stop and ask.
3. **Check `docs/test_strategy.md` if the task touches logic.** The
   safety invariants and test patterns there are authoritative.
4. **Look at the file tree.** If the task implies a new file, confirm
   where it goes against the structure in `CLAUDE.md`. Do not invent
   new directories or top-level folders.

---

## The three hard rules

These cannot be overridden by any request. Flag and refuse rather than
comply.

### Rule 1: Respect layer boundaries

Core has zero I/O. Integration never makes decisions. UI is dumb
orchestration. `tests/test_layer_boundaries.py` enforces this by scanning
imports. You cannot silently cross layers; the test will fail.

```python
# FORBIDDEN in src/core/*.py:
import requests
from fastapi import ...
from src.integration.ollama_adapter import OllamaAdapter

# FORBIDDEN in src/integration/*.py:
from src.ui.server import ...  # wrong direction

# FORBIDDEN everywhere:
import openai  # no cloud APIs
import anthropic  # no cloud APIs (Claude Code talks to Ollama, not Anthropic cloud)
```

If a task seems to require crossing a layer, propose restructuring, don't
cross. The usual pattern is: extract a pure function to Core, pass it
into the adapter via constructor injection.

### Rule 2: Do not substitute the locked model

KIN runs on `gemma4:e2b`. Do not propose `gemma4:e4b`, `gemma3n:e2b`
(which fabricates through the audio path — see `CLAUDE.md`), or any
other model. If a session suggests "you might get better results with a
larger model," refuse and flag. The model choice is load-bearing for the
prize narrative (runs on field hardware) and for the confirmed audio
pipeline behavior.

### Rule 3: No network calls, ever — in code or in tests

Production code never calls cloud APIs. `src/integration/sync_adapter.py`
produces RFL-compliant JSON for a local queue; it does not POST anywhere.

Tests never open a socket. `tests/conftest.py` monkeypatches
`socket.socket` to raise `RuntimeError("no network in tests")` for the
entire suite. If a test needs to hit an endpoint, use FastAPI's
`TestClient`, which runs in-process.

---

## Conventions for writing code

### Python

- **Type hints on every function.** `mypy --strict` passes on Core and
  Integration. UI (`server.py`) runs mypy strict on its own but FastAPI
  decorators leak `Any` — don't let that pollute other modules.
- **Pydantic v2 for every data structure that crosses a layer.** Raw
  dicts are fine within a function, never across a boundary.
- **Structured logging via `structlog`.** No `print()` except in
  `terminal_demo.py` (dev surface, user-facing output).
- **Tests mirror source one-to-one.** `src/core/safety_rules.py` →
  `tests/core/test_safety_rules.py`. If you create a new source file,
  create its test file in the same commit.
- **Async everywhere in the Integration and UI layers.** Core is
  sync-first; async only if the function already needs to be awaited.
- **File headers:** first line is a one-sentence docstring describing
  the file's single responsibility. If you can't state it in one
  sentence, the file is doing too much.
- **Comments explain WHY, not WHAT.** Code describes what it does;
  comments describe why it does it that way. A comment restating the
  code is noise.

### TypeScript (web UI)

- **React function components only.** No class components.
- **Component props typed explicitly,** no `any`, no `unknown` as a
  cop-out.
- **State via `useState` / `useReducer`.** No Redux, no Zustand, no
  external state library. SSE events + component state is sufficient.
- **SSE event handling in `src/lib/sse.ts`.** Components consume via
  the `useSSE` hook in `src/hooks/useSSE.ts`. Components don't speak
  directly to the server.
- **Types in `src/lib/types.ts` MUST track `src/core/rfl_schema.py`.**
  When you add a new SSE event type in Python, add it to `types.ts` in
  the same commit. `tests/ui/test_sse_contract.py` will fail if you
  forget.
- **Tailwind classes only.** No inline style objects except for
  dynamic values (e.g. `style={{ animationDelay: ... }}`). No CSS-in-JS
  libraries.
- **Design tokens in `tailwind.config.js`.** Don't introduce colors or
  radii inline. If you need a new token, add it to the config and
  document the decision in a comment.

### File organization

- **One component per file.** `Button.tsx` exports `Button` and
  nothing else. `RecordCard.tsx` exports `RecordCard`. Sub-components
  used only within one component can live in the same file; if they
  ever get reused, split them.
- **Hooks in `src/hooks/`, one per file.** `useSSE.ts`, not a
  `hooks.ts` catch-all.
- **Primitives in `src/components/primitives/`.** Composed components
  in `src/components/`. Don't mix.

---

## How to handle common situations

### "Add a new field to the RFL record"

1. Update `src/core/rfl_schema.py` — new Pydantic field with validation.
2. Add a test in `tests/core/test_rfl_schema.py` — field required/optional
   behavior, validation rules, JSON round-trip.
3. If the field should appear in the web UI: add the field to the
   `RecordCard` component, add a field test, update `types.ts`.
4. If the field is populated by the model: update the prompt (which means
   bumping the version — `intake_v3.txt` → `intake_v4.txt`), capture new
   fixtures with `scripts/capture_fixture.py`.
5. Commit message: `feat: add <field> to RFL record`.

### "Make the adapter timeout configurable"

If the request is to make the 25s timeout a parameter: already done,
it's the `timeout_s` constructor argument. Don't add a second mechanism.

If the request is to change the default: push back. The 25s ceiling is
derived from Phase 2.5 evidence (runaway loops observed at >25s). See
`decisions.md` for the rationale. Any change to this default requires a
new ADR.

### "Add a new language"

Refuse and flag. The four demo languages (EN/ES/AR/FA) are locked; the
other evaluated languages (French, Portuguese, Bengali, Ukrainian,
Swahili, Tigrinya, Amharic) were ruled out during Phase 2.5 for specific
reasons documented in `decisions.md`. Adding a new language would
require re-running Phase 2.5's probe protocol, which is out of scope for
the hackathon.

### "Add a multi-agent orchestrator"

Refuse. KIN has ONE agent. See `CLAUDE.md` scope exclusions. If the task
seems to require multi-agent thinking, the right move is almost always
to add a deterministic pre/post-processing step in the Integration layer,
not a second model call.

### "Write a test for this new code"

Test location mirrors source. Test names describe the invariant being
protected, not the implementation. Good:
`test_crisis_blocks_rfl_across_all_four_languages`. Bad:
`test_classify_function`.

If the test needs time, use `FakeClock` (Python) or `vi.useFakeTimers()`
(React). See `docs/test_strategy.md` §5.

If the test needs a model response, use a captured fixture. Do not call
Ollama from a test. If no fixture exists for what you need, capture one
via `scripts/capture_fixture.py` and commit it.

### "The test is slow / the test is flaky"

Slow tests are either hitting the network (fix: mock the adapter), doing
real I/O (fix: use `tmp_path` + in-memory), or using real timers (fix:
FakeClock / useFakeTimers). Fast tier (Core + Integration) must run in
under 10 seconds total. If a test breaks that budget, the test is wrong.

Flaky tests are almost always timing-dependent. Async tests without
`FakeClock` will eventually flake on loaded CI. If you see a flake, fix
the determinism root cause; do not retry-loop around it.

### "I want to add a new dependency"

Flag for approval before adding. Solo hackathon builds die from
dependency creep. Questions to answer in your flag:

- What problem does it solve that standard library / existing deps don't?
- What's its maintenance status?
- Does it work offline? (No Sentry, no Datadog, no cloud SaaS SDKs.)
- What's its license? (MIT / BSD / Apache fine; GPL requires flagging.)

Pre-approved deps for this project: pydantic, structlog, ollama (the
Python SDK), fastapi, uvicorn, pytest, pytest-asyncio, pytest-cov, ruff,
mypy, react, vite, tailwindcss, lucide-react, vitest, @testing-library/*,
playwright. Anything else: flag.

---

## Proposing an ADR amendment

If you believe a locked decision needs to change:

1. **Do not change the code first.** Propose the amendment in
   conversation.
2. **State what's locked now, what you're proposing, and why.**
3. **Reference the original ADR.** If you want to change decision 007,
   link to `docs/ADR/007-*.md`.
4. **Identify what else would change.** Amendments rarely stand alone;
   test strategy, directory layout, demo script often all move together.
5. **Wait for explicit approval** before editing. The user (or lead
   agent in the planning conversation) ratifies the amendment. Then the
   code work proceeds.

New ADR files go in `docs/ADR/` with an incrementing number:
`docs/ADR/008-<slug>.md`. Old ADRs are never deleted, only superseded.
Every ADR has a `Supersedes:` or `Standalone:` field at the top.

---

## Commit and push conventions

### Commit message format

```
<type>: <short description>

<optional body>

<optional trailers>
```

`<type>` is one of: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`,
`adr`. For early-phase commits the skill's format `phase-N: <what>` is
also accepted (e.g. `phase-4: ollama adapter`).

### Git identity

Local-only during build. `git config user.email mark@brazinski.us` and
`git config user.name "Mark Brazinski"` set at the repo level, not
globally.

### Push discipline

No pushes unless the user explicitly says so. Commit freely — `git
commit` is cheap and provides durability. `git push` is the user's
call; wait for "push it" or equivalent before running it.

A session running at 14:00 that has code to share with the remote
should stop at `git commit`, not `git push`.

---

## Pre-flight checklist before any PR / merge

Even solo, run through this on every meaningful chunk of work:

- [ ] `make test` passes locally (fast tier, Core + Integration + UI)
- [ ] `ruff check` clean
- [ ] `mypy --strict src/core src/integration` clean
- [ ] If you touched Python: `tests/test_layer_boundaries.py` passes
- [ ] If you touched SSE events: `tests/ui/test_sse_contract.py` passes
- [ ] If you changed a prompt: fixtures recaptured or the staleness check
      will fail
- [ ] No new dependencies without approval
- [ ] Commit message follows the format
- [ ] Evening push via script, not direct

---

## What NOT to do

From `CLAUDE.md`, repeated here because these come up as "help me
improve…" requests:

- ❌ Do not implement fine-tuning (Unsloth prize dropped)
- ❌ Do not substitute E4B or any non-E2B model
- ❌ Do not add multi-agent orchestration
- ❌ Do not add real ICRC/REFUNITE API integration
- ❌ Do not call cloud APIs (OpenAI, Anthropic cloud, Google cloud, etc.)
- ❌ Do not build mobile native apps
- ❌ Do not add mental-health therapy features — route to hotlines
- ❌ Do not add a React Clock Provider (use `vi.useFakeTimers()`)
- ❌ Do not run the full test suite on pre-commit (use the tiered setup)
- ❌ Do not capture fixtures before Day 5
- ❌ Do not bind FastAPI to `0.0.0.0` (always 127.0.0.1)
- ❌ Do not write business logic in `src/ui/server.py` or
      `src/ui/web/` (layer violation)

---

## A note on judgment

This file can't cover every situation. When in doubt:

- Does this serve the demo video or the code quality? If code quality
  for its own sake, probably not worth it.
- Does this add a failure mode under time pressure? If yes, flag.
- Would the user (solo dev, 25 days left) want to explain this on
  Day 15? If not, don't build it.
- Is this pattern already in the prototype or an existing module?
  Copy the pattern; don't invent a new one for the third instance.

The goal is a submittable demo on May 17 with code worth showing to
the judges. Everything else is subordinate.

---

**Last updated:** April 23, 2026 (PM) — Phase 5C initial draft