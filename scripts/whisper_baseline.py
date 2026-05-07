"""Day 10 Whisper baseline experiment — empirical signal only, no adapter changes."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from faster_whisper import WhisperModel

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = REPO_ROOT / "audio_samples"
RESULTS_DIR = REPO_ROOT / "results"

FIXTURES = [
    ("english_01.wav", "en"),
    ("spanish_01.wav", "es"),
    ("arabic_01.wav", "ar"),
    ("farsi_01.wav", "fa"),
    ("english_human_single.wav", "en"),
]

MODEL_SIZE = "medium"
COMPUTE_TYPE = "int8"  # CPU-friendly default; medium fp16 won't fit comfortably
DEVICE = "cpu"


def run_one(model: WhisperModel, audio_path: Path, task: str) -> dict:
    t0 = time.perf_counter()
    segments, info = model.transcribe(
        str(audio_path),
        task=task,
        beam_size=5,
    )
    text_parts: list[str] = []
    seg_count = 0
    for seg in segments:
        text_parts.append(seg.text)
        seg_count += 1
    elapsed = time.perf_counter() - t0
    return {
        "task": task,
        "text": "".join(text_parts).strip(),
        "latency_s": round(elapsed, 3),
        "detected_language": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "duration_s": round(float(info.duration), 3),
        "segments": seg_count,
    }


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[whisper-baseline] started {started_at}", file=sys.stderr)
    print(
        f"[whisper-baseline] loading {MODEL_SIZE} ({DEVICE}, {COMPUTE_TYPE}) "
        f"— first run downloads ~1.5GB",
        file=sys.stderr,
    )
    load_t0 = time.perf_counter()
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    load_elapsed = time.perf_counter() - load_t0
    print(f"[whisper-baseline] model ready in {load_elapsed:.1f}s", file=sys.stderr)

    results: list[dict] = []
    for fname, expected_lang in FIXTURES:
        audio_path = AUDIO_DIR / fname
        if not audio_path.exists():
            print(f"[whisper-baseline] MISSING: {audio_path}", file=sys.stderr)
            results.append(
                {
                    "fixture": fname,
                    "expected_language": expected_lang,
                    "error": "file not found",
                }
            )
            continue

        for task in ("transcribe", "translate"):
            print(f"[whisper-baseline] {fname} :: {task}", file=sys.stderr)
            try:
                run = run_one(model, audio_path, task)
                run["fixture"] = fname
                run["expected_language"] = expected_lang
                results.append(run)
                print(
                    f"  -> {run['latency_s']}s | lang={run['detected_language']} "
                    f"({run['language_probability']}) | {run['text'][:80]}",
                    file=sys.stderr,
                )
            except Exception as exc:  # noqa: BLE001 — baseline experiment, want all errors
                err = {
                    "fixture": fname,
                    "expected_language": expected_lang,
                    "task": task,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                results.append(err)
                print(f"  -> ERROR {err['error']}", file=sys.stderr)

    finished_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "model": f"faster-whisper:{MODEL_SIZE}",
        "compute_type": COMPUTE_TYPE,
        "device": DEVICE,
        "model_load_seconds": round(load_elapsed, 3),
        "results": results,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"whisper_baseline_{ts}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[whisper-baseline] wrote {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
