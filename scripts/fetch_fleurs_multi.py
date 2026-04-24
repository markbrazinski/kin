"""Pull N FLEURS clips each for a set of languages, write them padded and ready for probing."""

import subprocess
import sys
from pathlib import Path

import soundfile as sf
from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "audio_samples"
TARGET_CLIPS = 3
MIN_SEC = 5.0
MAX_SEC = 14.0  # avoid the ~21s crash zone; FLEURS has plenty under 14s
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"

# (fleurs_code, out_prefix, start_index)
# start_index picks up where prior batches left off so we don't clobber existing files
TARGETS = [
    ("uk_ua", "ukrainian", 4),
    ("fr_fr", "french", 2),
    ("pt_br", "portuguese", 1),
    ("bn_in", "bengali", 1),
]


def pad_in_place(path: Path) -> float:
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
         "-af", PAD_FILTER, "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(tmp)],
        check=True,
    )
    tmp.replace(path)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def main() -> int:
    for lang_code, prefix, start_idx in TARGETS:
        print(f"\n=== {prefix} ({lang_code}) ===", flush=True)
        ds = load_dataset("google/fleurs", lang_code, split="test", trust_remote_code=True)
        written = 0
        transcripts = []
        for sample in ds:
            audio = sample["audio"]
            array = audio["array"]
            sr = audio["sampling_rate"]
            duration = len(array) / sr
            if duration < MIN_SEC or duration > MAX_SEC:
                continue
            idx = start_idx + written
            out_path = OUT_DIR / f"{prefix}_{idx:02d}.wav"
            sf.write(out_path, array, sr, subtype="PCM_16")
            padded_duration = pad_in_place(out_path)
            transcripts.append((out_path.name, duration, padded_duration, sample.get("transcription", "")))
            print(f"  wrote {out_path.name}  raw={duration:.2f}s  padded={padded_duration:.2f}s", flush=True)
            written += 1
            if written >= TARGET_CLIPS:
                break
        print(f"  --- ground truth for {prefix} ---")
        for name, raw, padded, text in transcripts:
            print(f"  {name}: {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
