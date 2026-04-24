"""Farsi follow-up: 3 probes at num_predict=1500 to confirm stable completion without truncation."""

import base64
import glob
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import ollama

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
AUDIO = ROOT / "audio_samples" / "farsi_01.wav"
MODEL = "gemma4:e2b"
TEMP = 0.1
NUM_RUNS = 3
NUM_PREDICT = 1500
WALL_CLOCK_LIMIT = 30

PROMPT = (
    "You will receive an audio clip. Perform these two tasks in order "
    "and return as valid JSON with keys 'transcription' and "
    "'english_translation'. Do not include any other text, "
    "explanation, or commentary. Audio follows."
)


class _Timeout(Exception):
    pass


def _h(s, f):
    raise _Timeout("wall_clock_limit_exceeded")


def probe(run_n: int) -> dict:
    audio_b64 = base64.b64encode(AUDIO.read_bytes()).decode()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "timestamp": ts, "model": MODEL, "audio_file": str(AUDIO),
        "audio_bytes": AUDIO.stat().st_size, "temperature": TEMP,
        "num_predict": NUM_PREDICT, "wall_clock_limit_s": WALL_CLOCK_LIMIT,
        "prompt": PROMPT, "run": run_n,
    }

    t0 = time.perf_counter()
    signal.signal(signal.SIGALRM, _h)
    signal.alarm(WALL_CLOCK_LIMIT)
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT, "images": [audio_b64]}],
            options={"num_ctx": 8000, "temperature": TEMP, "num_predict": NUM_PREDICT},
        )
        record["latency_s"] = time.perf_counter() - t0
        record["response"] = response.model_dump(mode="json")
        record["outcome"] = "ok"
    except _Timeout:
        record["latency_s"] = time.perf_counter() - t0
        record["outcome"] = "wall_clock_timeout"
    except Exception as e:
        record["latency_s"] = time.perf_counter() - t0
        record["outcome"] = "exception"
        record["exception_type"] = type(e).__name__
        record["exception_message"] = str(e)
    finally:
        signal.alarm(0)

    out_path = RESULTS / f"farsi_retest_run{run_n}_{ts}.json"
    out_path.write_text(json.dumps(record, indent=2, default=str))
    record["_out_path"] = out_path
    return record


def classify(record: dict) -> tuple[str, str, str, str]:
    """Return (completed, transcription, english_translation, raw_content)."""
    if record["outcome"] != "ok":
        return (f"[{record['outcome']}]", "", "", "")
    resp = record["response"]
    done_reason = resp.get("done_reason", "?")
    content = resp.get("message", {}).get("content", "") or ""
    # done_reason == "stop" means natural EOS. "length" means num_predict cap. Anything else is odd.
    completed = {
        "stop": "natural EOS",
        "length": f"hit num_predict cap ({NUM_PREDICT})",
    }.get(done_reason, f"other ({done_reason})")

    # Best-effort extract of transcription / english_translation fields
    import re
    m = re.search(r"```json\s*(\{.*?)\s*```", content, re.DOTALL)
    blob = m.group(1) if m else content
    transcription = ""
    english = ""
    try:
        parsed = json.loads(blob) if blob.strip().startswith("{") and blob.strip().endswith("}") else None
        if parsed:
            transcription = str(parsed.get("transcription", "")).strip()
            english = str(parsed.get("english_translation", "")).strip()
    except Exception:
        pass
    return (completed, transcription, english, content)


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def load_prior_farsi() -> list[dict]:
    """Gather the original Test 3 Farsi runs for side-by-side context."""
    priors = []
    for path in sorted(glob.glob(str(RESULTS / "test3_farsi_run*.json"))):
        try:
            d = json.loads(Path(path).read_text())
            resp = d.get("response", {})
            done_reason = resp.get("done_reason", "?")
            content = resp.get("message", {}).get("content", "") or ""
            priors.append({
                "file": Path(path).name,
                "latency": d.get("latency_s"),
                "outcome": d.get("outcome"),
                "done_reason": done_reason,
                "content": content,
                "num_predict": 400,  # prior cap
            })
        except Exception as e:
            priors.append({"file": Path(path).name, "error": str(e)})
    return priors


def main() -> int:
    if not AUDIO.exists():
        print(f"MISSING: {AUDIO}", file=sys.stderr)
        return 1
    RESULTS.mkdir(exist_ok=True)
    print(f"farsi_retest: audio={AUDIO.name} num_predict={NUM_PREDICT} wall_clock={WALL_CLOCK_LIMIT}s")

    rows = []
    for i in range(1, NUM_RUNS + 1):
        print(f"run {i}/{NUM_RUNS}...", flush=True)
        record = probe(i)
        completed, transcription, english, raw = classify(record)
        print(f"  latency={record['latency_s']:.2f}s outcome={record['outcome']} completed={completed}")
        print(f"  transcription: {transcription[:100]!r}")
        rows.append({
            "run": i, "latency": record["latency_s"], "outcome": record["outcome"],
            "completed": completed, "transcription": transcription,
            "english": english, "raw": raw,
        })

    priors = load_prior_farsi()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = [
        f"# Farsi Retest — {ts}", "",
        f"Model: `{MODEL}`  Temperature: `{TEMP}`  "
        f"num_predict: **{NUM_PREDICT}** (prior Test 3 cap was 400)  "
        f"Wall-clock cap: `{WALL_CLOCK_LIMIT}s`  "
        f"Audio: `{AUDIO.name}`",
        "",
        "## Retest runs (num_predict=1500)",
        "",
        "| Run | Latency (s) | Completed? | Transcription (Persian) | English translation | My read |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lat = f"{r['latency']:.2f}" if isinstance(r["latency"], (int, float)) else "—"
        lines.append(
            f"| {r['run']} | {lat} | {r['completed']} | "
            f"{md_escape(r['transcription'])} | {md_escape(r['english'])} |  |"
        )

    lines += ["", "## Original Test 3 Farsi runs (num_predict=400) — for continuity", ""]
    if priors:
        lines += [
            "| File | Latency (s) | Outcome | done_reason | Raw content |",
            "|---|---|---|---|---|",
        ]
        for p in priors:
            if "error" in p:
                lines.append(f"| {p['file']} | — | error | — | {md_escape(p['error'])} |")
                continue
            lat = f"{p['latency']:.2f}" if isinstance(p.get("latency"), (int, float)) else "—"
            lines.append(
                f"| {p['file']} | {lat} | {p['outcome']} | {p['done_reason']} | "
                f"{md_escape(p['content'])} |"
            )
    else:
        lines.append("(no prior test3_farsi_run*.json files found)")

    # Mechanical observations
    lines += ["", "## Mechanical observations", ""]
    completed_counts: dict[str, int] = {}
    for r in rows:
        completed_counts[r["completed"]] = completed_counts.get(r["completed"], 0) + 1
    lines.append(f"- Total retest runs: {len(rows)}")
    for k, v in sorted(completed_counts.items()):
        lines.append(f"- Completed = \"{k}\": {v}/{len(rows)}")
    timeouts = sum(1 for r in rows if r["outcome"] == "wall_clock_timeout")
    lines.append(f"- Wall-clock timeouts ({WALL_CLOCK_LIMIT}s): {timeouts}/{len(rows)}")
    latencies = [r["latency"] for r in rows if isinstance(r["latency"], (int, float))]
    if latencies:
        lines.append(f"- Latency range: min={min(latencies):.2f}s  max={max(latencies):.2f}s")
    # Consistency across retest runs
    transcriptions = [r["transcription"] for r in rows if r["transcription"]]
    if len(transcriptions) >= 2:
        distinct = len(set(transcriptions))
        lines.append(f"- Distinct transcriptions across {len(transcriptions)} non-empty runs: {distinct}")

    summary = RESULTS / f"farsi_retest_summary_{ts}.md"
    summary.write_text("\n".join(lines) + "\n")
    print(f"\nsummary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
