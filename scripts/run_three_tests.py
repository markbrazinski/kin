"""Three-test harness for hypothesis probes against gemma4:e2b audio."""

import argparse
import base64
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import ollama

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MODEL = "gemma4:e2b"
TEMP = 0.1
NUM_RUNS = 3
WALL_CLOCK_LIMIT = 45

STANDARD_PROMPT = (
    "You will receive an audio clip. Perform these two tasks in order "
    "and return as valid JSON with keys 'transcription' and "
    "'english_translation'. Do not include any other text, "
    "explanation, or commentary. Audio follows."
)

ENGLISH_ONLY_PROMPT = (
    "Listen to the audio. Respond only in English.\n"
    "\n"
    "1. Provide an English translation of what the speaker said.\n"
    "2. If the speaker mentions a person being searched for, extract:\n"
    "   - Name (if stated)\n"
    "   - Age (if stated)\n"
    "   - Distinguishing features (if stated)\n"
    "3. If no person is being searched for, output: \"NO_PERSON_MENTIONED\"\n"
    "\n"
    "Respond only in English. Do not transcribe in the source language."
)


class TimeoutError_(Exception):
    pass


def _handler(signum, frame):
    raise TimeoutError_("wall_clock_limit_exceeded")


def probe(audio_path: Path, prompt: str, run_label: str) -> dict:
    """Single probe. Writes result JSON to results/{run_label}_{ts}.json. Returns record."""
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "timestamp": ts,
        "model": MODEL,
        "audio_file": str(audio_path),
        "audio_bytes": audio_path.stat().st_size,
        "temperature": TEMP,
        "prompt": prompt,
        "run_label": run_label,
    }

    t0 = time.perf_counter()
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(WALL_CLOCK_LIMIT)
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt, "images": [audio_b64]}],
            options={"num_ctx": 8000, "temperature": TEMP, "num_predict": 400},
        )
        record["latency_s"] = time.perf_counter() - t0
        record["response"] = response.model_dump(mode="json")
        record["outcome"] = "ok"
    except TimeoutError_:
        record["latency_s"] = time.perf_counter() - t0
        record["outcome"] = "wall_clock_timeout"
    except Exception as e:
        record["latency_s"] = time.perf_counter() - t0
        record["outcome"] = "exception"
        record["exception_type"] = type(e).__name__
        record["exception_message"] = str(e)
    finally:
        signal.alarm(0)

    out_path = RESULTS / f"{run_label}_{ts}.json"
    out_path.write_text(json.dumps(record, indent=2, default=str))
    return record


def extract_content(record: dict) -> str:
    if record.get("outcome") != "ok":
        return f"[{record.get('outcome')}]"
    try:
        return record["response"]["message"]["content"] or "[empty]"
    except (KeyError, TypeError):
        return "[no_content]"


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def run_test1() -> list[dict]:
    clips = [
        ("french", ROOT / "audio_samples" / "french_01.wav"),
        ("ukrainian", ROOT / "audio_samples" / "ukrainian_01.wav"),
        ("bengali", ROOT / "audio_samples" / "bengali_01.wav"),
        ("portuguese", ROOT / "audio_samples" / "portuguese_01.wav"),
    ]
    rows = []
    for lang, path in clips:
        if not path.exists():
            rows.append({"lang": lang, "run": 0, "outcome": "clip_missing", "path": str(path)})
            print(f"[test1] MISSING: {path}")
            continue
        for run_n in range(1, NUM_RUNS + 1):
            label = f"test1_english_output_{lang}_run{run_n}"
            print(f"[test1] {lang} run {run_n}...", flush=True)
            record = probe(path, ENGLISH_ONLY_PROMPT, label)
            content = extract_content(record)
            print(f"  latency={record['latency_s']:.2f}s outcome={record['outcome']}  content={content[:100]!r}")
            rows.append({
                "lang": lang, "run": run_n, "latency": record["latency_s"],
                "outcome": record["outcome"], "content": content, "clip": path.name,
            })
    return rows


def run_test2() -> list[dict]:
    # Reuse ukrainian_01.wav (Common Voice conversational) since it matches the spec profile.
    path = ROOT / "audio_samples" / "ukrainian_01.wav"
    rows = []
    if not path.exists():
        rows.append({"run": 0, "outcome": "clip_missing", "path": str(path)})
        return rows
    for run_n in range(1, NUM_RUNS + 1):
        label = f"test2_ukrainian_conv_run{run_n}"
        print(f"[test2] ukrainian_conv run {run_n}...", flush=True)
        record = probe(path, STANDARD_PROMPT, label)
        content = extract_content(record)
        print(f"  latency={record['latency_s']:.2f}s outcome={record['outcome']}  content={content[:100]!r}")
        rows.append({
            "run": run_n, "latency": record["latency_s"],
            "outcome": record["outcome"], "content": content, "clip": path.name,
        })
    return rows


def run_test3() -> list[dict]:
    # Uses clips staged by fetch script. Expect: farsi_01.wav, amharic_01.wav.
    rows = []
    for lang in ["farsi", "amharic"]:
        path = ROOT / "audio_samples" / f"{lang}_01.wav"
        if not path.exists():
            rows.append({"lang": lang, "run": 0, "outcome": "clip_missing", "path": str(path)})
            print(f"[test3] MISSING: {path}")
            continue
        for run_n in range(1, NUM_RUNS + 1):
            label = f"test3_{lang}_run{run_n}"
            print(f"[test3] {lang} run {run_n}...", flush=True)
            record = probe(path, STANDARD_PROMPT, label)
            content = extract_content(record)
            print(f"  latency={record['latency_s']:.2f}s outcome={record['outcome']}  content={content[:100]!r}")
            rows.append({
                "lang": lang, "run": run_n, "latency": record["latency_s"],
                "outcome": record["outcome"], "content": content, "clip": path.name,
            })
    return rows


def write_summary(t1_rows: list[dict], t2_rows: list[dict], t3_rows: list[dict]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = [f"# Three Hypothesis Tests — {ts}", "",
             f"Model: `{MODEL}`  Temperature: `{TEMP}`  Runs per case: `{NUM_RUNS}`  Wall-clock cap: `{WALL_CLOCK_LIMIT}s`",
             ""]

    # Test 1
    lines += ["## Test 1 — English-output translation hypothesis", "",
              "Prompt asked for English-only output and person-extraction. "
              "'Respected English only' column: mechanical check — does the model output "
              "contain non-ASCII characters from the source script (Cyrillic / Bengali / diacritic-heavy French)?",
              "",
              "| Language | Run | Latency (s) | Outcome | English translation | Respected English only? | My read |",
              "|---|---|---|---|---|---|---|"]
    for r in t1_rows:
        if r.get("outcome") in (None, "clip_missing"):
            lines.append(f"| {r['lang']} | — | — | clip_missing | — | — |  |")
            continue
        text = r.get("content", "")
        non_ascii = any(ord(c) > 127 for c in text)
        respected = "no (has non-ASCII)" if non_ascii else "yes"
        lat = f"{r['latency']:.2f}" if isinstance(r.get("latency"), (int, float)) else "—"
        lines.append(f"| {r['lang']} | {r['run']} | {lat} | {r['outcome']} | {md_escape(text)} | {respected} |  |")

    # Test 2
    lines += ["", "## Test 2 — Ukrainian conversational retest", "",
              "Standard transcription+translation prompt, on ukrainian_01.wav (Common Voice conversational clip).",
              "",
              "| Clip | Run | Latency (s) | Outcome | Output | My read |",
              "|---|---|---|---|---|---|"]
    for r in t2_rows:
        if r.get("outcome") in (None, "clip_missing"):
            lines.append(f"| — | — | — | clip_missing | — |  |")
            continue
        text = r.get("content", "")
        lat = f"{r['latency']:.2f}" if isinstance(r.get("latency"), (int, float)) else "—"
        lines.append(f"| {r['clip']} | {r['run']} | {lat} | {r['outcome']} | {md_escape(text)} |  |")

    # Test 3
    lines += ["", "## Test 3 — Farsi and Amharic baseline", "",
              "Standard prompt, FLEURS clips (fa_ir, am_et).",
              "",
              "| Language | Run | Latency (s) | Outcome | Output | My read |",
              "|---|---|---|---|---|---|"]
    for r in t3_rows:
        if r.get("outcome") in (None, "clip_missing"):
            lines.append(f"| {r['lang']} | — | — | clip_missing | — |  |")
            continue
        text = r.get("content", "")
        lat = f"{r['latency']:.2f}" if isinstance(r.get("latency"), (int, float)) else "—"
        lines.append(f"| {r['lang']} | {r['run']} | {lat} | {r['outcome']} | {md_escape(text)} |  |")

    # Mechanical findings
    findings: list[str] = []
    all_rows = [("test1", r) for r in t1_rows] + [("test2", r) for r in t2_rows] + [("test3", r) for r in t3_rows]
    timeouts = [(t, r) for t, r in all_rows if r.get("outcome") == "wall_clock_timeout"]
    exceptions = [(t, r) for t, r in all_rows if r.get("outcome") == "exception"]
    missing = [(t, r) for t, r in all_rows if r.get("outcome") == "clip_missing"]
    empty = [(t, r) for t, r in all_rows if r.get("content", "") in ("[empty]", "")]
    latencies = [r["latency"] for _, r in all_rows if isinstance(r.get("latency"), (int, float))]

    findings.append(f"- Total probes attempted: {sum(1 for _, r in all_rows if r.get('run', 0) > 0)}")
    findings.append(f"- Wall-clock timeouts: {len(timeouts)}"
                    + (f" (" + ", ".join(f"{t}/{r.get('lang','')} run {r.get('run')}" for t, r in timeouts) + ")" if timeouts else ""))
    findings.append(f"- Exceptions: {len(exceptions)}"
                    + (f" (" + ", ".join(f"{t}/{r.get('lang','')} run {r.get('run')}: {r.get('exception_type')}" for t, r in exceptions) + ")" if exceptions else ""))
    findings.append(f"- Empty responses: {len(empty)}")
    findings.append(f"- Missing clips (skipped): {len(missing)}"
                    + (f" (" + ", ".join(r.get("path","") for _, r in missing) + ")" if missing else ""))
    if latencies:
        findings.append(f"- Latency range: min={min(latencies):.2f}s  max={max(latencies):.2f}s  "
                        f"median={sorted(latencies)[len(latencies)//2]:.2f}s")

    # Test 1 language-compliance tally (mechanical only)
    t1_nonascii = sum(1 for r in t1_rows if r.get("outcome") == "ok" and any(ord(c) > 127 for c in r.get("content", "")))
    t1_total = sum(1 for r in t1_rows if r.get("outcome") == "ok")
    if t1_total:
        findings.append(f"- Test 1 \"respected English only\" check: {t1_total - t1_nonascii}/{t1_total} outputs were pure-ASCII")

    lines += ["", "## Key findings (mechanical only)", ""] + findings + [""]

    summary_path = RESULTS / f"three_tests_summary_{ts}.md"
    summary_path.write_text("\n".join(lines) + "\n")
    return summary_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true",
                    help="Assume farsi_01.wav / amharic_01.wav are already staged")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)

    print("=== TEST 1: English-output hypothesis ===")
    t1_rows = run_test1()

    print("\n=== TEST 2: Ukrainian conversational retest ===")
    t2_rows = run_test2()

    print("\n=== TEST 3: Farsi and Amharic baseline ===")
    t3_rows = run_test3()

    summary = write_summary(t1_rows, t2_rows, t3_rows)
    print(f"\nsummary written: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
