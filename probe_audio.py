"""Minimum-viable probe: does gemma4:e2b accept audio via the images field?"""

# Phase 2.5 recon tool — kept for ad-hoc future probes
# (e.g., "does language X still work after Ollama upgrade?").
#
# ASSUMPTIONS: input WAV is pre-padded (1000ms head silence +
# 500ms tail) and 16kHz mono. Callers are responsible for
# preprocessing. See CLAUDE.md Learned Audio Pipeline Constraints #1.
#
# Canonical preprocessing will move to src/integration/ollama_adapter.py
# in Phase 4. Do not duplicate padding logic here.

import argparse
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import ollama

ROOT = Path(__file__).parent
DEFAULT_MODEL = "gemma4:e2b"
DEFAULT_AUDIO = ROOT / "audio_samples" / "english_01.wav"

PROMPT = (
    "You will receive an audio clip. Perform these two tasks in order "
    "and return as valid JSON with keys 'transcription' and "
    "'english_translation'. Do not include any other text, "
    "explanation, or commentary. Audio follows."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--run-label", default="probe")
    args = ap.parse_args()

    if not args.audio.exists():
        print(f"ERROR: audio file not found at {args.audio}", file=sys.stderr)
        return 1

    audio_b64 = base64.b64encode(args.audio.read_bytes()).decode()
    print(f"audio file: {args.audio.name} ({args.audio.stat().st_size} bytes)")
    print(f"model: {args.model}  temperature: {args.temperature}")
    print("---")

    t0 = time.perf_counter()
    try:
        response = ollama.chat(
            model=args.model,
            messages=[
                {"role": "user", "content": PROMPT, "images": [audio_b64]}
            ],
            options={"num_ctx": 8000, "temperature": args.temperature, "num_predict": 400},
        )
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"EXCEPTION after {elapsed:.2f}s: {type(e).__name__}: {e}")
        return 2

    elapsed = time.perf_counter() - t0
    print(f"latency: {elapsed:.2f}s")
    print("--- message content ---")
    print(response.message.content)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "results" / f"{args.run_label}_{ts}.json"
    out_path.parent.mkdir(exist_ok=True)
    record = {
        "timestamp": ts,
        "model": args.model,
        "audio_file": str(args.audio),
        "audio_bytes": args.audio.stat().st_size,
        "temperature": args.temperature,
        "prompt": PROMPT,
        "latency_s": elapsed,
        "response": response.model_dump(mode="json"),
    }
    out_path.write_text(json.dumps(record, indent=2, default=str))
    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
