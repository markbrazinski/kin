"""Day 11 / Apr 29 — Gemma 4 E2B tool-calling stability sweep across EN/AR/FA.

Question: does the GREEN result from the Apr 28 Spanish hello-world
(scripts/gemma_extraction_helloworld.py) hold across the other three demo
languages? If yes, S3 (extraction integration) is unblocked. If no, the
extraction path must escalate to Boss-mode before Apr 29 orchestration work
proceeds.

Pass criteria per language:
  GREEN — all 5 runs PASS (clean tool call, correct name + relationship)
  AMBER — all 5 runs PASS or AMBIGUOUS (prose leakage or hallucinated age)
Fail criteria per language:
  RED       — any FAIL_* or ERROR
  HARD_FAIL — any FAIL_WITH_JSON_LIKE_CONTENT (tool param silently dropped)

Overall verdict:
  GREEN if all three languages GREEN
  AMBER if all three languages GREEN or AMBER, at least one AMBER
  RED if any language RED
  HARD_FAIL if any language HARD_FAIL

think=False is locked by ADR-003. Script prints response.message.thinking; if
non-None on any run, the lock has regressed and the test is invalidated.

Patterns ancestor: scripts/gemma_extraction_helloworld.py — same TOOL
definition, same per-run record shape, same classify() structure parameterized
per-language for expected name + relationship tokens.

Usage: .venv/bin/python scripts/gemma_extraction_multilang_sweep.py

Out of scope: production extraction pipeline, additional tool signatures,
languages beyond the three brief-specified inputs (EN/AR/FA), Spanish (already
cleared GREEN on Apr 28). No commits.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ollama

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from integration.ollama_adapter import MODEL, OPTIONS  # noqa: E402

RUNS_PER_LANG = 5

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
                        "(e.g., 'son', 'daughter', 'hijo', 'hija', "
                        "'ابن', 'پسر')."
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


@dataclass
class LangCase:
    """One language under test.

    name_substrings / relationship_substrings: lowercase token sets; PASS
    requires the model's output to contain at least one substring from each
    set (case-insensitive). Multiple variants per set acknowledge transliteration
    drift (e.g., the model may emit "Reza" or "رضا" for the Farsi case; both
    are correct).

    expected_age: int | None — None means the input did not state an age, so
    a non-null integer in the output is AMBIGUOUS_HALLUCINATED_AGE. If the
    input states an age (AR + FA cases), the model may emit it as integer;
    that's PASS, not AMBIGUOUS.
    """

    code: str
    label: str
    input_text: str
    name_substrings: tuple[str, ...]
    relationship_substrings: tuple[str, ...]
    expected_age: int | None
    records: list[dict[str, Any]] = field(default_factory=list)


CASES: tuple[LangCase, ...] = (
    LangCase(
        code="en",
        label="English",
        input_text="I'm looking for my son. His name is Carlos.",
        name_substrings=("carlos",),
        relationship_substrings=("son",),
        expected_age=None,
    ),
    LangCase(
        code="ar",
        label="Arabic",
        input_text=(
            "أبحث عن ابني محمد. عمره ثماني سنوات. فقدناه في مخيم الزعتري."
        ),
        # Mohamed/Mohammad/Muhammad and Arabic script محمد all acceptable.
        name_substrings=("محمد", "mohammed", "mohamed", "muhammad", "mohammad"),
        # ابن (son), my son (English calque), Arabic script ابني also acceptable.
        relationship_substrings=("ابن", "son"),
        expected_age=8,
    ),
    LangCase(
        code="fa",
        label="Farsi",
        input_text="من دنبال پسرم می‌گردم. اسمش رضا است. هشت سال دارد.",
        # Reza in Latin or رضا in Persian script.
        name_substrings=("رضا", "reza"),
        # پسر (son), Persian script پسرم also acceptable, English "son" calque.
        relationship_substrings=("پسر", "son"),
        expected_age=8,
    ),
)


def _tool_calls_to_jsonable(tool_calls: Any) -> list[dict[str, Any]]:
    """Normalize SDK tool_call objects to plain JSON-serializable dicts."""
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
    case: LangCase,
) -> tuple[str, str]:
    """Pure classification helper, parameterized per language case.

    Same status taxonomy as the Apr 28 hello-world classifier. The only
    differences are:
      - name + relationship checks consult case.name_substrings /
        case.relationship_substrings
      - expected_age is None means hallucinated-age check fires; if
        expected_age is set, an emitted integer matching it is PASS, and
        an emitted integer NOT matching it is FAIL_WRONG_VALUES (model
        misheard or invented).
    """
    content_clean = (content or "").strip()

    if not tool_calls:
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

    if not isinstance(full_name, str):
        return ("FAIL_BAD_ARGS", f"full_name is not a string: {type(full_name).__name__}")
    name_lower = full_name.lower()
    if not any(sub.lower() in name_lower for sub in case.name_substrings):
        return (
            "FAIL_WRONG_VALUES",
            f"full_name does not match any of {case.name_substrings}: {full_name!r}",
        )

    if not isinstance(relationship, str):
        return ("FAIL_BAD_ARGS", f"relationship is not a string: {type(relationship).__name__}")
    rel_lower = relationship.lower()
    if not any(sub.lower() in rel_lower for sub in case.relationship_substrings):
        return (
            "FAIL_WRONG_VALUES",
            f"relationship does not match any of {case.relationship_substrings}: {relationship!r}",
        )

    # bool is an int subclass — exclude True/False from the integer check.
    if isinstance(age, int) and not isinstance(age, bool):
        if case.expected_age is None:
            return (
                "AMBIGUOUS_HALLUCINATED_AGE",
                f"age stated as {age} but input gave no age",
            )
        if age != case.expected_age:
            return (
                "FAIL_WRONG_VALUES",
                f"age {age} does not match expected {case.expected_age}",
            )
        # else: PASS-shape age, fall through.

    # Reaching here means tool call is structurally valid with correct values.
    if content_clean:
        return (
            "AMBIGUOUS_PROSE_LEAKAGE",
            f"tool call OK but content non-empty ({len(content_clean)} chars)",
        )

    return ("PASS", "tool call structurally clean, values match input")


def one_run(
    client: ollama.Client,
    case: LangCase,
    run_index: int,
) -> dict[str, Any]:
    print()
    print(f"--- {case.label} run {run_index} ---")
    t0 = time.perf_counter()
    record: dict[str, Any] = {"lang": case.code, "run": run_index}
    try:
        response = client.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case.input_text},
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
        status, reason = classify(tool_calls_jsonable, raw_content or "", case)

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


def lang_verdict(records: list[dict[str, Any]]) -> str:
    """Reduce per-run statuses to a per-language verdict.

    HARD_FAIL > RED > AMBER > GREEN priority.
    """
    statuses = [r.get("classification", "ERROR") for r in records]
    if any(s == "FAIL_WITH_JSON_LIKE_CONTENT" for s in statuses):
        return "HARD_FAIL"
    if any(s == "ERROR" or s.startswith("FAIL_") for s in statuses):
        return "RED"
    if any(s.startswith("AMBIGUOUS_") for s in statuses):
        return "AMBER"
    return "GREEN"


def main() -> int:
    print("=" * 80)
    print("Gemma 4 E2B tool-calling stability sweep — EN / AR / FA")
    print("=" * 80)
    print(f"  model        : {MODEL}")
    print(f"  options      : {OPTIONS}")
    print(f"  think        : False  (ADR-003 lock)")
    print(f"  runs/lang    : {RUNS_PER_LANG}")
    print(f"  tool         : {TOOL['function']['name']}")

    client = ollama.Client()

    for case in CASES:
        print()
        print("=" * 80)
        print(f"LANGUAGE: {case.label} ({case.code})")
        print(f"  input    : {case.input_text!r}")
        print(f"  expected : name~={case.name_substrings} rel~={case.relationship_substrings} age={case.expected_age}")
        print("=" * 80)
        for i in range(1, RUNS_PER_LANG + 1):
            case.records.append(one_run(client, case, i))

    # Per-language aggregate tables
    print()
    print("=" * 80)
    print("PER-LANGUAGE AGGREGATES")
    print("=" * 80)
    for case in CASES:
        verdict = lang_verdict(case.records)
        print()
        print(f"  {case.label} ({case.code}) — verdict: {verdict}")
        print(
            f"    {'run':>3} | {'latency':>8} | {'eval':>5} | {'done':<8} | classification"
        )
        print(f"    {'-' * 3} | {'-' * 8} | {'-' * 5} | {'-' * 8} | {'-' * 40}")
        for r in case.records:
            latency = r.get("latency_s", "?")
            eval_c = r.get("eval_count", "?")
            done = r.get("done_reason", "?")
            cls = r.get("classification", "?")
            reason = r.get("classification_reason", "")
            print(
                f"    {r['run']:>3} | {str(latency):>8} | {str(eval_c):>5} | "
                f"{str(done):<8} | {cls}  ({reason})"
            )

    # Overall verdict
    verdicts = {case.code: lang_verdict(case.records) for case in CASES}
    print()
    print("=" * 80)
    print("OVERALL")
    print("=" * 80)
    for code, v in verdicts.items():
        print(f"  {code}: {v}")

    if any(v == "HARD_FAIL" for v in verdicts.values()):
        overall = "HARD_FAIL"
        exit_code = 2
    elif any(v == "RED" for v in verdicts.values()):
        overall = "RED"
        exit_code = 1
    elif any(v == "AMBER" for v in verdicts.values()):
        overall = "AMBER"
        exit_code = 0
    else:
        overall = "GREEN"
        exit_code = 0

    print()
    print(f"  OVERALL VERDICT: {overall}")
    print()
    if overall == "GREEN":
        print("  All three languages produced clean tool calls. S3 extraction work")
        print("  unblocked. ingest_audio can rely on tool-calling for EN/ES/AR/FA.")
    elif overall == "AMBER":
        print("  All three languages produced clean tool calls, with at least one")
        print("  AMBIGUOUS sub-status (prose leakage or hallucinated age). S3 work")
        print("  unblocked, but pipeline must add the AMBIGUOUS handling: parse")
        print("  tool_calls preferentially, suppress content when tool_calls present,")
        print("  validate optional fields against hallucination.")
    elif overall == "RED":
        print("  At least one language failed structurally. S3 BLOCKED. Escalate to")
        print("  Boss-mode before extraction integration. Possible mitigations:")
        print("  per-language prompt tweaks, language routing, fallback to structured")
        print("  output for affected languages.")
    else:  # HARD_FAIL
        print("  At least one language emitted JSON-shaped prose with tool_calls")
        print("  empty — Days 8-9 echo. Tool parameter appears to be silently dropped")
        print("  for that language. STOP. Check Ollama daemon + Python client")
        print("  versions. Escalate to Boss-mode before any further extraction work.")
    print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
