"""Phase 2.5 audio smoke test: sweep clips through gemma4:e2b with canonical preprocessing."""

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import ollama

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "audio_samples" / "sweep"
RESULTS_DIR = ROOT / "results"
MODEL = "gemma4:e2b"
TEMPERATURE = 0.1
NUM_RUNS = 3
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"
FILENAME_RE = re.compile(r"^(?P<language>[a-z]+)_(?P<nn>\d+)\.wav$")

PROMPT = (
    "You will receive an audio clip. Perform these two tasks in order "
    "and return as valid JSON with keys 'transcription' and "
    "'english_translation'. Do not include any other text, "
    "explanation, or commentary. Audio follows."
)


def preprocess(src: Path, dst: Path) -> None:
    """Pad head silence and resample to 16kHz mono WAV. Errors surface."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-af", PAD_FILTER,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            str(dst),
        ],
        check=True,
    )


def run_inference(audio_b64: str) -> tuple[float, dict]:
    t0 = time.perf_counter()
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT, "images": [audio_b64]}],
        options={"num_ctx": 8000, "temperature": TEMPERATURE},
    )
    elapsed = time.perf_counter() - t0
    return elapsed, response.model_dump(mode="json")


def extract_transcription(content: str) -> str:
    """Best-effort extraction of the transcription field for the summary table."""
    m = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
    blob = m.group(1) if m else content
    try:
        parsed = json.loads(blob)
        return str(parsed.get("transcription", "")).strip()
    except json.JSONDecodeError:
        return ""


def markdown_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    args = ap.parse_args()

    if not args.input_dir.is_dir():
        print(f"ERROR: input dir not found: {args.input_dir}", file=sys.stderr)
        return 1

    clips = sorted(p for p in args.input_dir.iterdir() if FILENAME_RE.match(p.name))
    if not clips:
        print(f"ERROR: no clips matching '<language>_<nn>.wav' in {args.input_dir}", file=sys.stderr)
        return 1

    RESULTS_DIR.mkdir(exist_ok=True)
    ts_run = datetime.now().strftime("%Y%m%d_%H%M%S")
    preprocessed_dir = RESULTS_DIR / f"preprocessed_{ts_run}"
    preprocessed_dir.mkdir()

    summary_rows: list[tuple[str, str, int, float, str]] = []

    for clip in clips:
        match = FILENAME_RE.match(clip.name)
        language = match.group("language")
        padded = preprocessed_dir / clip.name
        print(f"[{clip.name}] preprocessing...")
        preprocess(clip, padded)
        audio_b64 = base64.b64encode(padded.read_bytes()).decode()

        for run_n in range(1, NUM_RUNS + 1):
            print(f"[{clip.name}] run {run_n}/{NUM_RUNS}...", flush=True)
            elapsed, response_dict = run_inference(audio_b64)
            content = response_dict.get("message", {}).get("content", "") or ""
            transcription = extract_transcription(content)
            print(f"  latency: {elapsed:.2f}s  transcription: {transcription[:80]!r}")

            record = {
                "timestamp": datetime.now().isoformat(),
                "model": MODEL,
                "temperature": TEMPERATURE,
                "clip": clip.name,
                "language": language,
                "run": run_n,
                "preprocessing": {
                    "pad_filter": PAD_FILTER,
                    "target_format": "16000 Hz mono s16 WAV",
                },
                "prompt": PROMPT,
                "latency_s": elapsed,
                "response": response_dict,
            }
            out_path = RESULTS_DIR / f"sweep_{language}_{clip.stem}_run{run_n}_{ts_run}.json"
            out_path.write_text(json.dumps(record, indent=2, default=str))

            summary_rows.append((language, clip.name, run_n, elapsed, transcription))

    md_path = RESULTS_DIR / f"sweep_summary_{ts_run}.md"
    lines = [
        f"# Audio Smoke Sweep — {ts_run}",
        "",
        f"Model: `{MODEL}`  Temperature: `{TEMPERATURE}`  Runs per clip: `{NUM_RUNS}`",
        f"Preprocessing: `ffmpeg -af \"{PAD_FILTER}\"` → 16kHz mono s16 WAV",
        "",
        "Semantic match is human-filled after reading the per-run JSON files.",
        "",
        "| Language | Clip | Run | Latency (s) | Transcription | Semantic match |",
        "|---|---|---|---|---|---|",
    ]
    for language, clip_name, run_n, elapsed, transcription in summary_rows:
        lines.append(
            f"| {language} | {clip_name} | {run_n} | {elapsed:.2f} | "
            f"{markdown_escape(transcription)} |  |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    print(f"\nsummary: {md_path}")
    print(f"per-run JSON: {RESULTS_DIR}/sweep_*_{ts_run}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
