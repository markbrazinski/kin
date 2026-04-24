"""Pull 1 FLEURS clip each for Farsi (fa_ir) and Amharic (am_et), pad in place."""

import subprocess
import sys
from pathlib import Path

import soundfile as sf
from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "audio_samples"
MIN_SEC = 7.0
MAX_SEC = 13.0
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"
TARGETS = [("fa_ir", "farsi"), ("am_et", "amharic")]


def pad_in_place(path: Path) -> float:
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
         "-af", PAD_FILTER, "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(tmp)],
        check=True,
    )
    tmp.replace(path)
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def main() -> int:
    for lang_code, prefix in TARGETS:
        print(f"\n=== {prefix} ({lang_code}) ===", flush=True)
        ds = load_dataset("google/fleurs", lang_code, split="test", trust_remote_code=True)
        for sample in ds:
            audio = sample["audio"]
            dur = len(audio["array"]) / audio["sampling_rate"]
            if dur < MIN_SEC or dur > MAX_SEC:
                continue
            out_path = OUT_DIR / f"{prefix}_01.wav"
            sf.write(out_path, audio["array"], audio["sampling_rate"], subtype="PCM_16")
            padded_dur = pad_in_place(out_path)
            print(f"  wrote {out_path.name}  raw={dur:.2f}s  padded={padded_dur:.2f}s")
            print(f"  ground_truth: {sample.get('transcription','')}")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
