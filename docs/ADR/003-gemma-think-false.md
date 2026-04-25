# ADR-003: Gemma 4 E2B `think=False` on every `ollama.chat` call

**Date:** April 24, 2026 (Day 5)
**Status:** LOCKED
**Records:** `think=False` decision (PROJECT_PLAN §7 Locked, `scripts/gemma_hello.py` finding 2)

## Context

Gemma 4 E2B defaults to `think=True` when the SDK does not pass the
`think` parameter. With reasoning enabled, the model emits 1400-1800
tokens of self-deliberation in `message.thinking` before any content
is produced.

Phase 2.5's "stable at `num_predict=1500`" Farsi result was the think
block fitting under the 1500 ceiling — content emerged because there
was room left. The reasoning-mode behavior was present all along;
`num_predict=1500` just masked it. Day 4 Session 4 isolated the trap
at `num_predict=400` while building `scripts/gemma_hello.py`:

- without `think=False`: `done_reason="length"`, `eval_count=400`,
  `message.content` empty or cap-truncated mid-token,
  `message.thinking` 1400-1800 chars
- with `think=False`: latency 2.33s, `done_reason="stop"`,
  `eval_count=62`, `message.content` valid JSON,
  `message.thinking=None`

The lock was already entered into PROJECT_PLAN §7 Locked at Day 4 EOD
reconciliation. This ADR records the rationale; it does not amend the
lock.

## Decision

`ollama.chat(..., think=False)` on every call from the canonical
adapter. Hardcoded in `src/integration/ollama_adapter.py:_call_with_timeout`,
not exposed as a constructor argument or per-call option.

Rationale: KIN's adapter has one job — produce structured RFL output
from a voice clip in under 25 seconds. Reasoning traces are not part
of any KIN demo surface. Exposing `think` as a knob would mean every
caller has to know the right answer (always `False`); hardcoding
removes the foot-gun.

## Consequences

**Positive:**

- Inference budget collapses from `eval_count=400` (cap-truncated) to
  `eval_count=62` (natural EOS). Latency 2.33s on M4 Air at warm
  model — well inside the 25s adapter timeout.
- `message.content` carries the JSON the Pydantic schema expects;
  `InvalidToolCall` gets exercised against legitimate model
  malformations rather than reasoning-mode artifacts.
- One less knob in the adapter surface. ADR + module docstring +
  exception docstring all carry the lock language; future readers
  can't accidentally reintroduce `think=True`.

**Negative / accepted:**

- A KIN feature that genuinely wants reasoning traces (none anticipated
  in the May 18 scope) cannot enable it without modifying the adapter
  and updating ADR-003. Accepted — the alternative is a footgun.

## Followup

None. Adapter `_call_with_timeout` carries the lock in code; ADR-003
preserves the rationale.
