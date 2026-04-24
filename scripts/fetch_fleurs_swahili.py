"""Pull 3 Swahili clips from FLEURS and write them as audio_samples/swahili_06..08.wav."""

import sys
from pathlib import Path

import soundfile as sf
from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "audio_samples"
LANG = "sw_ke"  # FLEURS code for Swahili (Kenya)
SPLIT = "test"
TARGET_CLIPS = 3
MIN_SEC = 5.0
MAX_SEC = 15.0
START_INDEX = 6  # writes swahili_06, _07, _08 (preserves existing 01-05)


def main() -> int:
    print(f"loading FLEURS {LANG} {SPLIT} split (may download ~200MB on first run)...", flush=True)
    ds = load_dataset("google/fleurs", LANG, split=SPLIT, trust_remote_code=True)
    print(f"loaded {len(ds)} samples", flush=True)

    written = 0
    transcripts = []
    for i, sample in enumerate(ds):
        audio = sample["audio"]
        array = audio["array"]
        sr = audio["sampling_rate"]
        duration = len(array) / sr
        if duration < MIN_SEC or duration > MAX_SEC:
            continue
        idx = START_INDEX + written
        out_path = OUT_DIR / f"swahili_{idx:02d}.wav"
        sf.write(out_path, array, sr, subtype="PCM_16")
        transcripts.append((out_path.name, duration, sr, sample.get("transcription", "")))
        print(f"wrote {out_path.name}  duration={duration:.2f}s  sr={sr}", flush=True)
        written += 1
        if written >= TARGET_CLIPS:
            break

    print("\n--- ground truth transcriptions ---")
    for name, dur, sr, text in transcripts:
        print(f"{name}  ({dur:.2f}s, {sr} Hz):")
        print(f"  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
