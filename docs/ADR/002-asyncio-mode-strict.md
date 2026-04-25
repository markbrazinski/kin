# ADR-002: pytest asyncio_mode = "strict"

**Date:** April 24, 2026 (Day 4)
**Status:** LOCKED
**Amends:** docs/test_strategy.md §6, PROJECT_PLAN.md §6.5, docs/phase-5B-scaffolding.md

## Context

Day 3 scaffolding shipped `pyproject.toml` with `asyncio_mode = "strict"`.
Earlier planning docs (test_strategy §6, PROJECT_PLAN §6.5, phase-5B-
scaffolding) drafted `"auto"`; Day 3 scaffolding shipped `"strict"`.
Which was "the intent" is now unknowable — `"strict"` is what landed,
green, and reflects the repo's decorator convention.

The drift surfaced during Day 4 Session 1 (SystemClock, commit `473424c`).
The suite is green under `"strict"` because every async test already
carries explicit `@pytest.mark.asyncio` — the convention landed in
FakeClock's Day 3 test file and continued in SystemClock's Day 4 test.

## Decision

Keep `asyncio_mode = "strict"`. Update docs to match.

Rationale: code on disk is working, no regression pressure, and strict
makes async vs sync tests visually explicit at the decorator (small
readability win). Flipping to `"auto"` would be a lossless code change
but a pointless one — the repo's convention is already strict-compatible.

## Consequences

**Positive:**

- Docs match code; one less trap for a future fresh session.
- `@pytest.mark.asyncio` decorator stays explicit, which makes async
  boundaries visible at the test level.
- Matches PROJECT_PLAN §8 governance ("If this file and reality diverge,
  reality wins and this file gets updated same-day.").

**Negative / accepted:**

- Minor overhead: each new async test needs the decorator. Accepted —
  the alternative is implicit magic, which is a worse trade at this
  suite size.

## Followup

None. This ratifies the status quo; no code or test changes. Day 4
Session 2 commit carries the doc edits.
