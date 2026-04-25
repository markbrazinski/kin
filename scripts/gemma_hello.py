"""Day 4 bridge: clock-wired Python↔Ollama call, with a cancellation probe.

Not the canonical adapter. Superseded by
src/integration/ollama_adapter.py once that lands Day 5-6.
This file exists to:
  1. Prove SYSTEM_CLOCK + asyncio timeout race (per test_strategy.md §5)
     actually wraps a real ollama.chat call end-to-end.
  2. Document what asyncio.to_thread cancellation actually does to the
     underlying ollama.chat invocation — is the 25s timeout a Core-time
     guarantee or a daemon-time guarantee?

INVESTIGATION FINDING 1 — asyncio.to_thread cancellation semantics
==================================================================

When the timeout race fires (timer wins, call task is cancelled),
the worker thread wrapping ollama.chat continues running to natural
completion. Verified via _HangingClient diagnostic at 2.0s timeout:
  - task.cancelled() == True
  - task.done() == True
  - worker thread still alive in threading.enumerate()
  - mock chat() never returned

Implication: the 25s adapter timeout in PROJECT_PLAN §3 is a
Core-time guarantee only. Daemon-side computation continues
invisibly until natural completion. The HTTP request to Ollama
finishes in the background; the response is generated, sent,
and discarded client-side.

Day 5's canonical adapter inherits this semantic. Code comments
and structlog must be honest: timeout is "Core returns within
25s," not "daemon stops within 25s."

INVESTIGATION FINDING 2 — Gemma 4 E2B reasoning-mode trap
=========================================================

Gemma 4 E2B defaults to think=True when the SDK does not pass the
think parameter. With reasoning enabled, the model emits 1400-1800
tokens of self-deliberation in message.thinking before any content
is produced.

Symptoms observed (num_predict=400, no think parameter):
  - done_reason: "length" (hit cap, not natural EOS)
  - eval_count: 400 (full budget consumed)
  - message.content: empty string or cap-truncated mid-token
  - message.thinking: 1400-1800 chars of internal reasoning

Phase 2.5's "stable at num_predict=1500" Farsi result was the think
block fitting under the 1500 ceiling — content emerged because there
was room left. The reasoning-mode behavior was present all along;
num_predict=1500 just masked it.

Resolution: ollama.chat(..., think=False) disables reasoning mode.
English transcription with think=False:
  - latency: 2.33s
  - done_reason: "stop" (natural EOS)
  - eval_count: 62
  - message.content: valid JSON with both required keys
  - message.thinking: None

NOTE: this bridge file as committed does NOT pass think=False —
the cruft is intentional. Day 5's canonical adapter at
src/integration/ollama_adapter.py is the production location for
think=False; this bridge is superseded once that lands. ADR-003
will record the decision when Day 5's adapter commits.

Ollama SDK: `ollama` Python client 0.6.1. Distinct semver track from
the Ollama daemon (CLAUDE.md ≥0.20.3 lock refers to the daemon, not
the Python client).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import threading
from pathlib import Path
from typing import Any

# src/ is on pythonpath via pyproject pytest config, but scripts/ runs
# outside that context — add src/ explicitly so the Clock + SystemClock
# imports resolve the same way they will when Day 5's adapter lands.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ollama  # noqa: E402  (after sys.path mutation above)

from core.clock import Clock  # noqa: E402
from integration.system_clock import SYSTEM_CLOCK  # noqa: E402

MODEL = "gemma4:e2b"
AUDIO_DEFAULT = REPO_ROOT / "audio_samples" / "english_01.wav"

# Prompt duplicated from probe_audio.py verbatim. Lifting to a single
# authoritative location is a Day 5 concern when ollama_adapter.py
# decides where prompts live.
PROMPT = (
    "You will receive an audio clip. Perform these two tasks in order "
    "and return as valid JSON with keys 'transcription' and "
    "'english_translation'. Do not include any other text, "
    "explanation, or commentary. Audio follows."
)

# num_predict=1500. Phase 2.5's "confirmed stable across EN/ES/AR/FA"
# claim was actually Farsi-only validation. The 1500 ceiling was
# masking Gemma 4 E2B's reasoning-mode behavior — see INVESTIGATION
# FINDING 2 in the module docstring above. Day 5's canonical adapter
# uses think=False with num_predict=400 instead.
OPTIONS: dict[str, Any] = {
    "num_ctx": 8000,
    "temperature": 0.1,
    "num_predict": 1500,
}


class InferenceTimeoutError(Exception):
    """Raised when the timer wins the race against the inference call."""


async def _call_with_timeout(
    client: Any,
    messages: list[dict[str, Any]],
    options: dict[str, Any],
    clock: Clock,
    timeout_s: float,
) -> tuple[Any, asyncio.Task[Any], float]:
    """Race ollama.chat against clock.sleep; return (response, call_task, elapsed).

    Returns the response on success. Raises InferenceTimeoutError on timeout,
    attaching the cancelled call task as `.call_task` so investigate_cancellation
    can inspect its post-cancel state. Pattern matches test_strategy.md §5
    lines 419-432.
    """
    start = clock.monotonic()
    call = asyncio.create_task(
        asyncio.to_thread(client.chat, model=MODEL, messages=messages, options=options)
    )
    timer = asyncio.create_task(clock.sleep(timeout_s))
    done, pending = await asyncio.wait(
        {call, timer}, return_when=asyncio.FIRST_COMPLETED
    )
    for p in pending:
        p.cancel()
    elapsed = clock.monotonic() - start
    if call in done:
        # Swallow the timer's CancelledError on cleanup.
        for p in pending:
            try:
                await p
            except asyncio.CancelledError:
                pass
        return call.result(), call, elapsed
    err = InferenceTimeoutError(
        f"inference exceeded {timeout_s}s (elapsed={elapsed:.2f}s)"
    )
    # Attach the cancelled call task for post-mortem inspection. We do NOT
    # await it here — the whole point of the investigation is to observe
    # what state it's in right after cancel() and whether the thread is
    # alive independent of the task.
    err.call_task = call  # type: ignore[attr-defined]
    err.elapsed = elapsed  # type: ignore[attr-defined]
    raise err


async def run_happy_path(
    audio_path: Path, clock: Clock = SYSTEM_CLOCK, timeout_s: float = 25.0
) -> int:
    """Real Ollama call. Returns 0 on success, non-zero on failure."""
    if not audio_path.exists():
        print(f"ERROR: audio file not found at {audio_path}", file=sys.stderr)
        return 1

    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()
    messages = [{"role": "user", "content": PROMPT, "images": [audio_b64]}]

    rel = audio_path.relative_to(REPO_ROOT)
    size = audio_path.stat().st_size
    print("happy path")
    print(f"  audio: {rel} ({size} bytes)")
    print(f"  model: {MODEL}  num_predict={OPTIONS['num_predict']}")

    try:
        response, _call, elapsed = await _call_with_timeout(
            ollama, messages, OPTIONS, clock, timeout_s
        )
    except InferenceTimeoutError as e:
        print(f"  TIMEOUT: {e}")
        return 2

    if hasattr(response, "message"):
        content = response.message.content
        done_reason = getattr(response, "done_reason", None) or "?"
    else:
        content = response.get("message", {}).get("content", "")
        done_reason = response.get("done_reason", "?")
    print(f"  latency: {elapsed:.2f}s")
    print(f"  done_reason: {done_reason}")
    print(f"  content: {content[:400]!r}{'...' if len(content) > 400 else ''}")
    return 0


class _HangingClient:
    """Mock whose .chat blocks the worker thread forever.

    threading.Event().wait() blocks the OS thread (not a coroutine),
    which is the realistic analog of "ollama.chat is mid-HTTP and not
    returning yet." asyncio.Event().wait() would require a running
    loop in the worker thread, which asyncio.to_thread does not provide.
    """

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.returned = threading.Event()
        self._block = threading.Event()  # never set — forces a hang

    def chat(self, **_kwargs: Any) -> None:
        self.entered.set()
        self._block.wait()  # blocks forever
        self.returned.set()  # should never reach this


async def investigate_cancellation(
    clock: Clock = SYSTEM_CLOCK, timeout_s: float = 2.0
) -> str:
    """Force the timer to win; inspect post-cancel state.

    Returns a one-line summary string for the FINDINGS block. Uses
    SYSTEM_CLOCK (not FakeClock) because the question is about real
    cancellation propagation through asyncio.to_thread, not virtual
    time accounting. Timeout set to 2.0s so we observe the real
    behavior without sitting through a 25s wait.
    """
    client = _HangingClient()
    messages = [{"role": "user", "content": "irrelevant", "images": []}]
    threads_before = {t.ident for t in threading.enumerate()}

    print("cancellation investigation")
    print(f"  starting call against _HangingClient (timeout_s={timeout_s})...")

    start_mono = clock.monotonic()
    try:
        await _call_with_timeout(client, messages, OPTIONS, clock, timeout_s)
    except InferenceTimeoutError as e:
        elapsed = getattr(e, "elapsed", clock.monotonic() - start_mono)
        call: asyncio.Task[Any] = e.call_task  # type: ignore[attr-defined]
    else:
        return "UNEXPECTED: timeout path did not fire"

    # Let the event loop process the cancellation before we inspect.
    await asyncio.sleep(0)

    cancelled = call.cancelled()
    done = call.done()
    entered = client.entered.is_set()
    returned_early = client.returned.is_set()
    threads_after = {t.ident for t in threading.enumerate()}
    orphan_threads = threads_after - threads_before

    print(f"  timer fired; elapsed={elapsed:.2f}s")
    print(f"  call task state: cancelled={cancelled}, done={done}")
    print(f"  mock chat() entered worker thread: {entered}")
    print(f"  mock chat() returned (thread completed): {returned_early}")
    print(f"  orphan thread ids (alive after cancel): {sorted(orphan_threads)}")

    # Build the one-line summary. The predicted outcome is:
    #   cancelled=True, done=True, returned_early=False, orphans non-empty.
    # Anything different is a surprise worth naming.
    if cancelled and entered and not returned_early and orphan_threads:
        summary = (
            f"task cancelled={cancelled}, done={done}, but worker thread still "
            f"alive ({len(orphan_threads)} orphan); chat() never returned. "
            f"asyncio.to_thread cancellation is a Core-time guarantee only; "
            f"the worker thread continues running to natural completion."
        )
    elif cancelled and not entered:
        summary = (
            "task cancelled before worker thread even started — investigation "
            "inconclusive; increase await time before cancel or re-run."
        )
    elif returned_early:
        summary = (
            "UNEXPECTED: mock chat() returned despite being blocked on "
            "threading.Event. Something woke it. Re-investigate."
        )
    else:
        summary = (
            f"inconclusive — cancelled={cancelled}, done={done}, "
            f"entered={entered}, returned_early={returned_early}, "
            f"orphan_count={len(orphan_threads)}. Day 5 to re-investigate "
            f"with adapter instrumentation."
        )
    print(f"  conclusion: {summary}")

    # Release the mock's block so the orphan thread can exit cleanly at
    # process shutdown. This does NOT affect the finding — we already
    # observed state while the thread was still blocked.
    client._block.set()
    return summary


def _print_findings_block(happy_rc: int, investigation_summary: str) -> None:
    print()
    print("FINDINGS")
    print("  Q1. When call.cancel() fires, does the worker thread running")
    print("      ollama.chat actually terminate?")
    print(f"      → {investigation_summary}")
    print()
    print("  Q2. What happens to the Ollama daemon's computation?")
    print("      → Not directly observed in this run (mock client, no")
    print("        daemon request). Implication: if the thread keeps")
    print("        running, the HTTP request the real ollama.chat made")
    print("        keeps streaming; the daemon finishes generating and")
    print("        the response is discarded on the client side. Day 5")
    print("        can confirm with a real deliberately-slow inference.")
    print()
    print("  Q3. What does this mean for the 25s timeout?")
    print("      → 25s is a Core-time guarantee (Core sees the")
    print("        InferenceTimeoutError at t=25s and moves on). It is")
    print("        NOT a daemon-time guarantee — the daemon may still")
    print("        be computing after Core has given up. Day 5 adapter")
    print("        must treat 'timeout fired' as 'stop trusting this")
    print("        response', not 'stop the daemon.'")
    print()
    print(f"  Happy path exit code: {happy_rc}")


async def _amain(args: argparse.Namespace) -> int:
    happy_rc = 0
    summary = "not run"
    if args.mode in ("happy", "both"):
        happy_rc = await run_happy_path(args.audio)
        print()
    if args.mode in ("investigate", "both"):
        summary = await investigate_cancellation()
    if args.mode == "both":
        _print_findings_block(happy_rc, summary)
    return happy_rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("happy", "investigate", "both"), default="both")
    ap.add_argument("--audio", type=Path, default=AUDIO_DEFAULT)
    args = ap.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
