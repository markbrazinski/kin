"""Multi-turn RFL-state coherence probe for Gemma 4 E2B (Phase 4 de-risk, text-only)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import ollama
from pydantic import BaseModel, Field, ValidationError


MODEL = "gemma4:e2b"
HOST = "http://localhost:11434"
TIMEOUT_S = 25.0
TEMPERATURE = 0.1
NUM_PREDICT = 1500
TRIALS_PER_LANG = 3
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "results" / "multi_turn_probe.jsonl"


SYSTEM_PROMPT = """You are a strict JSON state updater for a humanitarian family-reunification record.

You will receive:
1. CURRENT_STATE: a JSON object representing what is already known.
2. USER_UTTERANCE: a new message from the user (may be in any language).

Your job: return the UPDATED state as a single JSON object.

RULES:
- UPDATE existing fields with new information. Do NOT clobber prior-turn information.
- If a field is already populated and the new utterance does not contradict it, keep the existing value.
- If the new utterance adds information to a field, merge it (e.g. append to distinguishing_marks).
- Return the COMPLETE updated state, including all prior-turn fields, not just the delta.
- NEVER invent facts the user did not state. If a field is unknown, leave it as null or [].
- If the user states or implies the subject is under 18, set minor_flag to true.
- If the user states self-harm, violence to self, or an immediate crisis, set crisis_flag to true.

SCHEMA (all fields required in output):
{
  "full_name": string | null,
  "aka": [string],
  "relationship_to_seeker": string | null,
  "seeker_name": string | null,
  "age": integer | null,
  "last_seen_location": string | null,
  "last_seen_date": string | null,
  "distinguishing_marks": [string],
  "languages": [string],
  "crisis_flag": boolean,
  "minor_flag": boolean
}

FIELD SEMANTICS:
- full_name: The name of the MISSING PERSON being searched for.
- seeker_name: The name of the person DOING THE SEARCHING (the
  one speaking to you).
- relationship_to_seeker: How the missing person is related to
  the seeker (son, daughter, parent, sibling, spouse, etc.).

The user is searching for a missing family member. Extract
information about BOTH the missing person and the seeker when
present in the utterance.

OUTPUT: Return ONLY the JSON object. No prose, no markdown fences, no commentary."""


RFL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "full_name": {"type": ["string", "null"]},
        "aka": {"type": ["array", "null"], "items": {"type": "string"}},
        "relationship_to_seeker": {"type": ["string", "null"]},
        "seeker_name": {"type": ["string", "null"]},
        "age": {"type": ["integer", "null"]},
        "last_seen_location": {"type": ["string", "null"]},
        "last_seen_date": {"type": ["string", "null"]},
        "distinguishing_marks": {"type": ["array", "null"], "items": {"type": "string"}},
        "languages": {"type": ["array", "null"], "items": {"type": "string"}},
        "crisis_flag": {"type": "boolean"},
        "minor_flag": {"type": "boolean"},
    },
    "required": [
        "full_name",
        "aka",
        "relationship_to_seeker",
        "seeker_name",
        "age",
        "last_seen_location",
        "last_seen_date",
        "distinguishing_marks",
        "languages",
        "crisis_flag",
        "minor_flag",
    ],
}


TURNS: dict[str, list[str]] = {
    "farsi": [
        "من دنبال پسرم می‌گردم. اسمش رضا است.",
        "او هشت سال دارد. دو هفته پیش در مرز ترکیه گمش کردم.",
        "یک نشان روی گونه راستش دارد.",
    ],
    "arabic": [
        "أبحث عن ابنتي. اسمها فاطمة.",
        "عمرها ستة أعوام. فقدناها في مخيم الزعتري منذ شهر.",
        "ترتدي قلادة فضية من جدتها.",
    ],
}


VARIANTS = ("unconstrained", "constrained")


class RFLState(BaseModel):
    full_name: str | None = None
    aka: list[str] = Field(default_factory=list)
    relationship_to_seeker: str | None = None
    seeker_name: str | None = None
    age: int | None = None
    last_seen_location: str | None = None
    last_seen_date: str | None = None
    distinguishing_marks: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    crisis_flag: bool = False
    minor_flag: bool = False


def empty_state() -> dict[str, Any]:
    return RFLState().model_dump()


def is_populated(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, str)) and len(value) == 0:
        return False
    return True


def populated_fields(state: dict[str, Any]) -> set[str]:
    tracked = {
        "full_name",
        "aka",
        "relationship_to_seeker",
        "seeker_name",
        "age",
        "last_seen_location",
        "last_seen_date",
        "distinguishing_marks",
        "languages",
    }
    return {k for k in tracked if is_populated(state.get(k))}


def call_model(
    client: ollama.Client,
    state: dict[str, Any],
    utterance: str,
    variant: str,
    retry_appendix: str | None = None,
) -> tuple[str, int]:
    user_content = (
        f"CURRENT_STATE:\n{json.dumps(state, ensure_ascii=False)}\n\n"
        f"USER_UTTERANCE:\n{utterance}"
    )
    if retry_appendix:
        user_content += f"\n\n{retry_appendix}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "options": {"temperature": TEMPERATURE, "num_predict": NUM_PREDICT},
        "stream": False,
    }
    if variant == "constrained":
        kwargs["format"] = RFL_JSON_SCHEMA
    # variant == "unconstrained" → no format kwarg at all

    t0 = time.monotonic()
    response = client.chat(**kwargs)
    latency_ms = int((time.monotonic() - t0) * 1000)
    content = response["message"]["content"]
    return content, latency_ms


def parse_state(raw: str) -> tuple[dict[str, Any] | None, bool]:
    """Parse + validate. Returns (state_or_none, coerced_age_flag)."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None, False

    coerced_age = False
    if isinstance(obj, dict) and isinstance(obj.get("age"), str):
        age_str = obj["age"].strip()
        try:
            obj["age"] = int(age_str)
            coerced_age = True
        except ValueError:
            pass  # let Pydantic reject

    try:
        validated = RFLState.model_validate(obj)
    except ValidationError:
        return None, coerced_age
    return validated.model_dump(), coerced_age


def run_turn(
    client: ollama.Client,
    state: dict[str, Any],
    utterance: str,
    variant: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one turn. Returns (new_state_or_prior, turn_record)."""
    prior_populated = populated_fields(state)
    try:
        raw, latency_ms = call_model(client, state, utterance, variant)
    except ollama.RequestError as exc:
        if "Connection refused" in str(exc):
            raise
        return state, {
            "turn_latency_ms": 0,
            "parsed_ok": False,
            "coerced_age": False,
            "state_after": state,
            "fields_gained_this_turn": [],
            "fields_lost_this_turn": [],
            "error": f"inference_fail: RequestError: {str(exc)[:200]}",
        }
    except Exception as exc:
        return state, {
            "turn_latency_ms": 0,
            "parsed_ok": False,
            "coerced_age": False,
            "state_after": state,
            "fields_gained_this_turn": [],
            "fields_lost_this_turn": [],
            "error": f"inference_fail: {type(exc).__name__}: {str(exc)[:200]}",
        }

    parsed, coerced = parse_state(raw)
    total_latency = latency_ms

    if parsed is None:
        try:
            raw2, latency2 = call_model(
                client,
                state,
                utterance,
                variant,
                retry_appendix="RETURN ONLY VALID JSON, NO PROSE. The previous response did not parse.",
            )
            total_latency += latency2
            parsed, coerced_retry = parse_state(raw2)
            coerced = coerced or coerced_retry
        except Exception as exc:
            return state, {
                "turn_latency_ms": total_latency,
                "parsed_ok": False,
                "coerced_age": coerced,
                "state_after": state,
                "fields_gained_this_turn": [],
                "fields_lost_this_turn": [],
                "error": f"retry_fail: {type(exc).__name__}: {str(exc)[:200]}",
            }

    if parsed is None:
        return state, {
            "turn_latency_ms": total_latency,
            "parsed_ok": False,
            "coerced_age": coerced,
            "state_after": state,
            "fields_gained_this_turn": [],
            "fields_lost_this_turn": [],
            "error": "parse_fail_after_retry",
        }

    new_populated = populated_fields(parsed)
    gained = sorted(new_populated - prior_populated)
    lost = sorted(prior_populated - new_populated)
    return parsed, {
        "turn_latency_ms": total_latency,
        "parsed_ok": True,
        "coerced_age": coerced,
        "state_after": parsed,
        "fields_gained_this_turn": gained,
        "fields_lost_this_turn": lost,
        "error": None,
    }


def evaluate_trial(final_state: dict[str, Any]) -> tuple[bool, str | None]:
    required_populated = [
        "full_name",
        "age",
        "last_seen_location",
        "distinguishing_marks",
    ]
    missing = [f for f in required_populated if not is_populated(final_state.get(f))]
    if missing:
        return False, f"missing_or_clobbered: {missing}"

    minor_ok = final_state.get("minor_flag") is True
    age_val = final_state.get("age")
    if not minor_ok and isinstance(age_val, int) and age_val < 18:
        minor_ok = True
    if not minor_ok:
        return False, "minor_flag_not_set"

    return True, None


def run_trial(
    client: ollama.Client,
    language: str,
    trial_num: int,
    variant: str,
) -> dict[str, Any]:
    state = empty_state()
    turn_records = []
    for i, utterance in enumerate(TURNS[language], start=1):
        state, record = run_turn(client, state, utterance, variant)
        record_out: dict[str, Any] = {
            "turn": i,
            "latency_ms": record["turn_latency_ms"],
            "parsed_ok": record["parsed_ok"],
            "coerced_age": record["coerced_age"],
            "state_after": record["state_after"],
            "fields_gained_this_turn": record["fields_gained_this_turn"],
            "fields_lost_this_turn": record["fields_lost_this_turn"],
        }
        if record["error"]:
            record_out["error"] = record["error"]
        turn_records.append(record_out)

    passed, failure_reason = evaluate_trial(state)
    return {
        "language": language,
        "trial": trial_num,
        "variant": variant,
        "pass": passed,
        "turns": turn_records,
        "final_state": state,
        "failure_reason": failure_reason,
    }


def print_summary(results: list[dict[str, Any]]) -> None:
    counts: dict[str, dict[str, int]] = {
        lang: {"unconstrained": 0, "constrained": 0} for lang in ("farsi", "arabic")
    }
    for r in results:
        if r["pass"]:
            counts[r["language"]][r["variant"]] += 1

    print("\n| Lang   | Unconstrained | Constrained | Delta |")
    print("|--------|---------------|-------------|-------|")
    for lang in ("farsi", "arabic"):
        u = counts[lang]["unconstrained"]
        c = counts[lang]["constrained"]
        delta = c - u
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"| {lang:<6} | {u}/3           | {c}/3         | {delta_str:<5} |")

    print()
    for lang in ("farsi", "arabic"):
        u = counts[lang]["unconstrained"]
        c = counts[lang]["constrained"]
        print(f"{lang.upper()}: unconstrained {u}/3, constrained {c}/3")

    u_all = all(counts[l]["unconstrained"] >= 2 for l in ("farsi", "arabic"))
    c_all = all(counts[l]["constrained"] >= 2 for l in ("farsi", "arabic"))

    print()
    if c_all and u_all:
        print("VERDICT: LOCK TIER 2. format=<schema> OPTIONAL.")
    elif c_all and not u_all:
        print("VERDICT: LOCK TIER 2. format=<schema> MANDATORY Integration invariant.")
    elif u_all and not c_all:
        print("VERDICT: INVESTIGATE. Unconstrained passed but constrained did not — probably a schema bug.")
    else:
        print("VERDICT: FALL BACK TO TIER 1.")


def main() -> int:
    try:
        client = ollama.Client(host=HOST, timeout=TIMEOUT_S)
        client.list()
    except Exception as exc:
        msg = str(exc)
        if (
            "Connection refused" in msg
            or "ConnectError" in type(exc).__name__
            or "ConnectionError" in type(exc).__name__
        ):
            print(
                f"ERROR: cannot reach Ollama at {HOST}. Is `ollama serve` running?",
                file=sys.stderr,
            )
            return 2
        print(f"ERROR: ollama client init failed: {type(exc).__name__}: {msg}", file=sys.stderr)
        return 2

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for language in ("farsi", "arabic"):
            for trial_num in range(1, TRIALS_PER_LANG + 1):
                for variant in VARIANTS:
                    print(
                        f"[{language} trial {trial_num}/{TRIALS_PER_LANG} {variant}] running...",
                        flush=True,
                    )
                    try:
                        trial_result = run_trial(client, language, trial_num, variant)
                    except ollama.RequestError as exc:
                        if "Connection refused" in str(exc):
                            print(
                                f"ERROR: lost connection to Ollama at {HOST}. Is `ollama serve` running?",
                                file=sys.stderr,
                            )
                            return 2
                        raise
                    results.append(trial_result)
                    f.write(json.dumps(trial_result, ensure_ascii=False) + "\n")
                    f.flush()
                    verdict = (
                        "PASS"
                        if trial_result["pass"]
                        else f"FAIL ({trial_result['failure_reason']})"
                    )
                    print(f"  → {verdict}")

    print_summary(results)
    print(f"\nResults written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
