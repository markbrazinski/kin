"""Day 11 Session — Gemma 4 E2B tool-calling hello-world (Apr 29 decision gate).

Question: does gemma4:e2b under think=False emit clean native tool calls via
Ollama's tools=[...] parameter, or does it silently drop the parameter the
way format=<schema> did on Days 8-9?

Decision-gate consequences:
  GREEN  → Apr 29 orchestration uses tool-calling; adapter gains a
           tool_call(messages, tools) method mirroring translate().
  AMBER  → tool-calling with prose-leakage handling: parse tool_calls
           preferentially, fall back to JSON-in-content extractor.
  RED    → fall back to structured output via prompt + Pydantic
           validation. Acknowledge Days 8-9 risk; budget prompt
           iteration like prose_spike.
  HARD_FAIL → tool parameter behaves like format= did on Days 8-9
              (silently dropped). Check Ollama daemon + Python client
              versions before further investigation.

think=False is locked by ADR-003. Script also prints
response.message.thinking; if non-None, the lock has regressed at the SDK
level and the test is invalidated.

Patterns ancestor: scripts/translate_safety_keywords.py (sync ollama.Client
shape, repo-bootstrap idiom). Per-run record + aggregate verdict modeled on
scripts/prose_spike.py.

Usage: .venv/bin/python scripts/gemma_extraction_helloworld.py

Out of scope: production extraction pipeline (Apr 29-30), additional tool
signatures, additional languages, additional input sentences, transcription
pipeline wiring. No commits.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import ollama

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from integration.ollama_adapter import MODEL, OPTIONS  # noqa: E402

RUNS = 5
INPUT_TEXT = "Estoy buscando a mi hijo. Se llama Carlos."

SYSTEM_PROMPT = (
    "You are an intake assistant. When the user describes a missing person, "
    "call extract_intake_fields with the fields the user stated. Do not "
    "invent fields the user did not state — pass null for unknown values."
)

TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "extract_intake_fields",
        "description": (
            "Extract intake fields about a missing person from the speaker's "
            "statement."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {
                    "type": "string",
                    "description": "Full name of the missing person.",
                },
                "relationship": {
                    "type": "string",
                    "description": (
                        "Speaker's relationship to the missing person "
                        "(e.g., 'son', 'daughter', 'hijo', 'hija')."
                    ),
                },
                "age": {
                    "type": ["integer", "null"],
                    "description": (
                        "Age of the missing person if stated; null if not stated."
                    ),
                },
            },
            "required": ["full_name", "relationship"],
        },
    },
}


def _tool_calls_to_jsonable(tool_calls: Any) -> list[dict[str, Any]]:
    """Convert SDK tool_call objects into plain JSON-serializable dicts.

    The Ollama Python SDK returns tool calls as Pydantic-ish objects with
    .function.name / .function.arguments. We normalize to plain dicts so
    the diagnostic output is unambiguous and copy-pasteable into the
    findings doc.
    """
    if not tool_calls:
        return []
    out: list[dict[str, Any]] = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            fn = tc.get("function")
        else:
            fn = getattr(tc, "function", None)
        if fn is None:
            out.append({"raw": repr(tc)})
            continue
        if isinstance(fn, dict):
            name = fn.get("name")
            args = fn.get("arguments")
        else:
            name = getattr(fn, "name", None)
            args = getattr(fn, "arguments", None)
        out.append({"name": name, "arguments": args})
    return out


def classify(
    tool_calls: list[dict[str, Any]],
    content: str,
) -> tuple[str, str]:
    """Pure classification helper. Returns (status, reason).

    Statuses:
      PASS                          — exactly one tool call, name + values OK
      AMBIGUOUS_PROSE_LEAKAGE       — PASS + non-empty content alongside
      AMBIGUOUS_HALLUCINATED_AGE    — PASS shape but age is non-null integer
      FAIL_NO_TOOL_CALLS            — no tool_calls at all, no JSON-shaped content
      FAIL_WITH_JSON_LIKE_CONTENT   — Days 8-9 echo: empty tool_calls but
                                      content has JSON with expected keys
      FAIL_MULTIPLE_TOOL_CALLS      — >1 tool calls (unexpected)
      FAIL_WRONG_NAME               — function name mismatch
      FAIL_BAD_ARGS                 — arguments missing or unparseable
      FAIL_WRONG_VALUES             — full_name doesn't contain Carlos OR
                                      relationship doesn't match hijo/son
    """
    content_clean = (content or "").strip()

    if not tool_calls:
        # Days 8-9 echo check: did the model output JSON-shaped prose with
        # the expected keys instead of using the tool channel?
        looks_like_json = False
        try:
            parsed = json.loads(content_clean)
            if isinstance(parsed, dict) and (
                "full_name" in parsed or "relationship" in parsed
            ):
                looks_like_json = True
        except (json.JSONDecodeError, ValueError):
            looks_like_json = False
        if looks_like_json:
            return (
                "FAIL_WITH_JSON_LIKE_CONTENT",
                "tool_calls empty but content is JSON with expected keys",
            )
        return ("FAIL_NO_TOOL_CALLS", "no tool_calls and no JSON-shaped content")

    if len(tool_calls) > 1:
        return (
            "FAIL_MULTIPLE_TOOL_CALLS",
            f"expected 1 tool call, got {len(tool_calls)}",
        )

    call = tool_calls[0]
    name = call.get("name")
    if name != "extract_intake_fields":
        return ("FAIL_WRONG_NAME", f"expected extract_intake_fields, got {name!r}")

    args = call.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return ("FAIL_BAD_ARGS", "arguments is a string but not valid JSON")
    if not isinstance(args, dict):
        return ("FAIL_BAD_ARGS", f"arguments is not a dict: {type(args).__name__}")

    full_name = args.get("full_name", "")
    relationship = args.get("relationship", "")
    age = args.get("age", None)

    if not isinstance(full_name, str) or "carlos" not in full_name.lower():
        return (
            "FAIL_WRONG_VALUES",
            f"full_name does not contain 'Carlos': {full_name!r}",
        )

    rel_lower = relationship.lower() if isinstance(relationship, str) else ""
    if "hijo" not in rel_lower and "son" not in rel_lower:
        return (
            "FAIL_WRONG_VALUES",
            f"relationship does not match hijo/son: {relationship!r}",
        )

    # Structurally valid. Check for AMBIGUOUS sub-cases.
    # bool is an int subclass — exclude True/False from the hallucinated-age check.
    if isinstance(age, int) and not isinstance(age, bool):
        return (
            "AMBIGUOUS_HALLUCINATED_AGE",
            f"age stated as {age} but input gave no age",
        )

    if content_clean:
        return (
            "AMBIGUOUS_PROSE_LEAKAGE",
            f"tool call OK but content non-empty ({len(content_clean)} chars)",
        )

    return ("PASS", "tool call structurally clean, values match input")


def one_run(client: ollama.Client, run_index: int) -> dict[str, Any]:
    print()
    print(f"=== Run {run_index} ===")
    t0 = time.perf_counter()
    record: dict[str, Any] = {"run": run_index}
    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": INPUT_TEXT},
            ],
            tools=[TOOL],
            options=OPTIONS,
            think=False,
        )
        elapsed = time.perf_counter() - t0
        msg = getattr(response, "message", None)
        raw_tool_calls = getattr(msg, "tool_calls", None) if msg is not None else None
        raw_content = getattr(msg, "content", "") if msg is not None else ""
        raw_thinking = getattr(msg, "thinking", None) if msg is not None else None

        tool_calls_jsonable = _tool_calls_to_jsonable(raw_tool_calls)
        status, reason = classify(tool_calls_jsonable, raw_content or "")

        record.update(
            {
                "latency_s": round(elapsed, 3),
                "eval_count": getattr(response, "eval_count", None),
                "prompt_eval_count": getattr(response, "prompt_eval_count", None),
                "done_reason": getattr(response, "done_reason", None),
                "total_duration": getattr(response, "total_duration", None),
                "tool_calls": tool_calls_jsonable,
                "content": raw_content or "",
                "thinking": raw_thinking,
                "classification": status,
                "classification_reason": reason,
            }
        )

        print(f"  latency_s         : {record['latency_s']}")
        print(f"  eval_count        : {record['eval_count']}")
        print(f"  prompt_eval_count : {record['prompt_eval_count']}")
        print(f"  done_reason       : {record['done_reason']}")
        print(f"  thinking          : {raw_thinking!r}")
        print(f"  content           : {(raw_content or '')!r}")
        print(f"  tool_calls        : {json.dumps(tool_calls_jsonable, ensure_ascii=False, indent=2)}")
        print(f"  classification    : {status}  ({reason})")
    except Exception as e:  # noqa: BLE001 — surface every failure
        elapsed = time.perf_counter() - t0
        record.update(
            {
                "latency_s": round(elapsed, 3),
                "error_class": type(e).__name__,
                "error_msg": str(e),
                "classification": "ERROR",
                "classification_reason": f"{type(e).__name__}: {e}",
            }
        )
        print(f"  ERROR             : {type(e).__name__}: {e}")
        print("  classification    : ERROR")
    return record


def main() -> int:
    print("=" * 80)
    print("Gemma 4 E2B tool-calling hello-world (Apr 29 decision gate)")
    print("=" * 80)
    print(f"  model        : {MODEL}")
    print(f"  options      : {OPTIONS}")
    print(f"  think        : False  (ADR-003 lock)")
    print(f"  runs         : {RUNS}")
    print(f"  input        : {INPUT_TEXT!r}")
    print(f"  tool         : {TOOL['function']['name']}")
    print(f"  tool params  : {list(TOOL['function']['parameters']['properties'].keys())}")
    print(f"  required     : {TOOL['function']['parameters']['required']}")

    client = ollama.Client()
    records: list[dict[str, Any]] = []
    for i in range(1, RUNS + 1):
        records.append(one_run(client, i))

    # Aggregate table
    print()
    print("=" * 80)
    print("AGGREGATE")
    print("=" * 80)
    print(
        f"  {'run':>3} | {'latency':>8} | {'eval':>5} | {'done_reason':<12} | "
        f"classification"
    )
    print(f"  {'-' * 3} | {'-' * 8} | {'-' * 5} | {'-' * 12} | {'-' * 32}")
    for r in records:
        latency = r.get("latency_s", "?")
        eval_c = r.get("eval_count", "?")
        done = r.get("done_reason", "?")
        cls = r.get("classification", "?")
        reason = r.get("classification_reason", "")
        print(
            f"  {r['run']:>3} | {str(latency):>8} | {str(eval_c):>5} | "
            f"{str(done):<12} | {cls}  ({reason})"
        )

    # Verdict
    statuses = [r.get("classification", "ERROR") for r in records]
    has_hard_fail = any(s == "FAIL_WITH_JSON_LIKE_CONTENT" for s in statuses)
    has_error_or_fail = any(
        s == "ERROR" or s.startswith("FAIL_") for s in statuses
    )
    has_ambiguous = any(s.startswith("AMBIGUOUS_") for s in statuses)
    all_pass = all(s == "PASS" for s in statuses)
    all_pass_or_ambig = all(
        s == "PASS" or s.startswith("AMBIGUOUS_") for s in statuses
    )

    print()
    print("=" * 80)
    if has_hard_fail:
        verdict = "HARD_FAIL"
        exit_code = 2
        print(f"VERDICT: {verdict}")
        print("=" * 80)
        print(
            "  At least one run had empty tool_calls but JSON-shaped content "
            "with expected keys."
        )
        print(
            "  This is the Days 8-9 echo: tool parameter appears to have been "
            "silently dropped,"
        )
        print(
            "  the way format=<schema> was. Check Ollama daemon + Python "
            "client versions before"
        )
        print("  further investigation. Apr 29 falls back to structured output.")
    elif has_error_or_fail:
        verdict = "RED"
        exit_code = 1
        print(f"VERDICT: {verdict}")
        print("=" * 80)
        print(
            "  At least one run failed structurally (no tool_calls, wrong "
            "name, bad args, or"
        )
        print(
            "  wrong values), or raised an exception. Tool-calling is not "
            "stable enough for"
        )
        print(
            "  an Apr 29 dependency. Fall back to structured output via "
            "prompt + Pydantic"
        )
        print("  validation. Budget prompt-iteration time like prose_spike.")
    elif all_pass:
        verdict = "GREEN"
        exit_code = 0
        print(f"VERDICT: {verdict}")
        print("=" * 80)
        print(
            "  All 5 runs produced clean tool calls with correct name and "
            "values."
        )
        print(
            "  Apr 29 orchestration uses tools=[...] API. Adapter gains a "
            "tool_call(messages,"
        )
        print("  tools) method mirroring translate().")
    elif all_pass_or_ambig and has_ambiguous:
        verdict = "AMBER"
        exit_code = 0
        print(f"VERDICT: {verdict}")
        print("=" * 80)
        print(
            "  All 5 runs are PASS or AMBIGUOUS (prose alongside tool call, "
            "or hallucinated"
        )
        print(
            "  age). Tool-calling works but Apr 29 must add prose-leakage "
            "handling: parse"
        )
        print(
            "  tool_calls preferentially, fall back to JSON-in-content "
            "extractor; suppress"
        )
        print(
            "  content when tool_calls is present; validate that optional "
            "fields aren't filled"
        )
        print("  with hallucinated values.")
    else:
        verdict = "RED"
        exit_code = 1
        print(f"VERDICT: {verdict} (unhandled status combination)")
        print("=" * 80)
        print(f"  statuses: {statuses}")

    print()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
