# ADR: Web UI as Primary Demo Surface

**Date:** April 23, 2026 (PM)
**Status:** LOCKED
**Supersedes:** UI layer specification in Phase 4 ADR (April 23, AM) — "terminal + minimal web"
**Amends:** CLAUDE.md — three lines called out at end

## Context

The locked Phase 3D storyboard already depends on visual elements that terminal output cannot produce naturally: record cards, live waveform insets, completeness meters, color-coded border state changes (amber on `flag_minor`, red on `escalate_crisis`, green on transliteration match), persistent inline labels, and side-by-side panels for the transliteration-match wow moment. Honest reading of the storyboard says the demo is already half a web UI; the original ADR glossed this as "terminal with overlays" and underspecified.

Two additional signals pushed this revision:

1. The judge-facing artifact is a 2:20 video. Visual legibility of state changes is the strongest predictor of demo recall, especially for Glenn Cameron's humanitarian lens and for mobile playback without audio.
2. The Ollama Special Tech prize criterion "streaming tool calls — visible in the demo" lands meaningfully harder with a live function-call panel than with terminal log lines.

## Decision

The web UI is the primary recorded demo surface for the intake-side flow. The terminal remains the dev environment, the test-runner surface, and the caseworker-side interface (Claude Code pointed at Ollama's Anthropic-compat endpoint — unchanged).

This is not a fallback arrangement. After the Day 14 `safety-net-v1` tag, the web UI is committed.

## Scope (locked)

**In scope — intake web UI MVP:**

- Single-page React app, Tailwind + shadcn/ui
- Served locally by a FastAPI backend that wraps the same `ollama_adapter.py` the Integration layer already owns
- State streaming via Server-Sent Events (one-way: backend → UI)
- Components: record card, live waveform inset, function-call trace side panel, completeness meter, live timer, static baseline label, colored state borders, persistent inline labels (e.g., "Minor detected → child-protection schema activated"), transliteration-match split panel + match card
- One view. No routing. No auth. No settings. No history. No user management. FastAPI binds to 127.0.0.1 only.

**Out of scope — enforced:**

- Multi-screen navigation, authentication, user management
- Records list / search / edit-history UI (records write to local JSON; no persistence UI)
- Mobile or responsive layouts (demo hardware is MacBook Air M4)
- Dark-mode toggle, theming, settings panel
- Export UI beyond a single keyboard shortcut or button
- Any network egress of any kind

**Caseworker beat unchanged:** Claude Code pointed at `localhost:11434/v1` remains the caseworker-review surface. That beat stays terminal-forward and flexes Ollama's Anthropic-compat layer. The contrast between the visual intake UI and the Claude Code terminal review is now an intentional feature: same Gemma 4 E2B model, two surfaces, two personas.

## Architecture impact

No change to the three-layer hexagonal model.

- **UI layer:** adds `src/ui/web/` (React app) and `src/ui/server.py` (FastAPI wrapping the existing adapter)
- **Integration layer:** no new adapters. FastAPI calls the same `ollama_adapter.py`. Canonical audio padding, timeout, and logging remain in one place.
- **Core layer:** untouched. `rfl_schema.py`, `safety_rules.py`, `scoring.py`, `language_matrix.py` unchanged.

The web server is dumb orchestration. All decisions continue to come from Core. Any PR that adds business logic to `src/ui/web/` or `src/ui/server.py` is a layer violation and must be flagged.

## Storyboard reconciliation (Phase 5.7 follow-up, not blocking)

Two storyboard beats reference terminal-forward framing and need one-line updates in Phase 5.7:

1. **Spanish fill (0:50–1:22):** "Terminal shows `extract_name()` and `extract_relationship()` firing" → "function-call trace panel shows `extract_name()` and `extract_relationship()` firing." Same information, rendered in a styled side panel. Omar Sanseviero's technical-depth lens is preserved — trace still visible, still named, still live.
2. **Transliteration match (1:22–1:57):** 1-second structlog flash → same 1-second flash, rendered as a highlight on the function-call trace panel. Mechanism still visible.

Caseworker review beat (2:04–2:14) is unchanged — Claude Code in terminal.

## Recording contingency

**Cutoff for reverting to terminal-forward: Day 14, `safety-net-v1` tag.**

If by Day 14 the web UI is not clean enough to record the safety-net video, revert to the terminal-forward storyboard and record the safety net there. Cost: ~20 hours of UI work sunk. Benefit preserved: the locked storyboard remains achievable in terminal form, so this is a real contingency, not theoretical.

After Day 14: committed. No re-shoots in terminal form. This cutoff exists specifically to prevent week-3 indecision.

## Build budget

Hard ceiling: **20 hours across Days 1–10** for the intake web UI. If tracking over 25 hours, revert to terminal immediately regardless of Day 14. The web UI is a demo surface, not a product. It does not earn more than 25% of remaining build time.

## Test strategy impact

- FastAPI routes: unit-tested with `TestClient`, Ollama adapter mocked. ~15 tests.
- React components: interaction tests for state-change components (border transitions, completeness meter, function-call panel updates). ~15 tests.
- E2E: one Playwright test walking the Spanish-fill happy path against a mocked adapter. One, not ten — we care about recorded video, not browser-automation coverage.
- Target unchanged (100+). Web UI contributes ~30; Core and Integration continue to carry the bulk.

## Consequences

**Positive:**

- Stronger visual identity for the 2:20 video — state changes legible at mobile playback sizes without audio
- Streaming-tool-calls Ollama beat lands harder, tightening the Ollama Special Tech prize angle
- Record card reads as "humanitarian tool" more legibly than a terminal session for the Glenn Cameron framing
- Dual-surface contrast (intake web / caseworker terminal) becomes intentional

**Negative / accepted:**

- ~20 hours of UI work that doesn't exist in the terminal-forward plan
- New failure mode: a React build breaks the demo. Mitigated by Day 14 cutoff and by keeping the UI adapter-thin and stateless.
- One more surface to debug under time pressure in week 3

---

## Required CLAUDE.md edits (to ratify this ADR)

1. **Demo requirements, item 1:** add `via web UI` clause
   > "MUST WORK: Audio input in English, Spanish, Arabic, Farsi via web UI → transcription + translation → Gemma 4 E2B reasoning → valid RFL tool call → structured JSON output. ALL OFFLINE."

2. **Demo requirements, item 6:** reverse polarity
   > ~~"NICE TO HAVE: Simple web UI wrapping the terminal demo."~~
   > "MUST WORK: Terminal dev surface remains operational for tests and debugging."

3. **"What NOT to build" section:** replace the UI exclusion line
   > ~~"UIs beyond terminal + minimal web."~~
   > "UIs beyond the locked single-page intake web app + terminal caseworker review. No multi-screen, no auth, no history views — see ADR dated April 23 PM."

4. **File/directory structure block:** add web subdirectory under `src/ui/`

## Running Summary delta

```
Architecture: Tier 2, hexagonal 3-layer + web UI intake surface (LOCKED)
Demo surface: React web UI (intake) + Claude Code terminal (caseworker)
Web UI budget: 20 hrs, Days 1-10; cutoff Day 14
```