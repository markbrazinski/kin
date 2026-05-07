"""Day 10 Session 5 — Whisper FLEURS baseline for the 3 expansion survivors (fr/uk/bn).

Diagnostic-only. Untracked. Validates that faster-whisper medium can
recover intelligible transcriptions for fr/uk/bn before they land in
IMPLEMENTED_LANGS.

Pattern: scripts/whisper_baseline.py — direct WhisperModel call, NOT
through whisper_adapter.WhisperAdapter (the adapter raises
UnsupportedLanguage pre-Phase-5). One model load (~47s), three short
inferences (~7s each).

For each language:
  1. Fetch one FLEURS clip in the 5-14s window (matches existing
     fetch_fleurs_multi.py constraint).
  2. ffmpeg head-silence pad — same PAD_FILTER as the adapter.
  3. Whisper transcribe with task="transcribe", language=<code>.
  4. Capture: filename, ground-truth, Whisper output, similarity ratio,
     latency, pass/fail verdict.
  5. Drop rule: text length <5 chars OR detected language ≠ requested
     with low probability OR visibly degenerate output → fail.

Output: results/language_expansion_baseline_<TS>.md (gitignored).

Usage: .venv/bin/python scripts/expand_whisper_baseline.py
"""

from __future__ import annotations

import difflib
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
from datasets import load_dataset
from faster_whisper import WhisperModel

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = REPO_ROOT / "audio_samples"
RESULTS_DIR = REPO_ROOT / "results"

MIN_SEC = 5.0
MAX_SEC = 14.0
PAD_FILTER = "adelay=1000|1000,apad=pad_dur=0.5"

# (whisper_lang_code, fleurs_dataset_code, file_prefix, display_name)
SURVIVORS: tuple[tuple[str, str, str, str], ...] = (
    ("fr", "fr_fr", "french_validation", "French"),
    ("uk", "uk_ua", "ukrainian_validation", "Ukrainian"),
    ("bn", "bn_in", "bengali_validation", "Bengali"),
)

MODEL_SIZE = "medium"
COMPUTE_TYPE = "int8"
DEVICE = "cpu"


def fetch_fleurs_clip(fleurs_code: str, prefix: str) -> tuple[Path, str]:
    """Fetch one FLEURS clip in the 5-14s window. Return (audio_path, ground_truth)."""
    print(f"[fleurs] loading google/fleurs '{fleurs_code}' (test split)", file=sys.stderr)
    ds = load_dataset(
        "google/fleurs", fleurs_code, split="test", trust_remote_code=True
    )
    for sample in ds:
        audio = sample["audio"]
        array = audio["array"]
        sr = audio["sampling_rate"]
        duration = len(array) / sr
        if duration < MIN_SEC or duration > MAX_SEC:
            continue
        out_path = AUDIO_DIR / f"{prefix}.wav"
        sf.write(out_path, array, sr, subtype="PCM_16")
        ground_truth = str(sample.get("transcription", "")).strip()
        print(
            f"[fleurs] wrote {out_path.name} duration={duration:.2f}s "
            f"ground_truth_chars={len(ground_truth)}",
            file=sys.stderr,
        )
        return out_path, ground_truth
    raise RuntimeError(f"no FLEURS clip in {MIN_SEC}-{MAX_SEC}s window for {fleurs_code}")


def pad_in_place(path: Path) -> None:
    """ffmpeg head-silence padding, mirrors fetch_fleurs_multi.py:pad_in_place."""
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(path),
            "-af", PAD_FILTER,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            str(tmp),
        ],
        check=True,
    )
    tmp.replace(path)


def whisper_transcribe(
    model: WhisperModel, audio_path: Path, lang: str
) -> dict[str, object]:
    t0 = time.perf_counter()
    segments, info = model.transcribe(
        str(audio_path),
        task="transcribe",
        language=lang,
        beam_size=5,
    )
    text_parts: list[str] = []
    seg_count = 0
    for seg in segments:
        text_parts.append(seg.text)
        seg_count += 1
    elapsed = time.perf_counter() - t0
    return {
        "text": "".join(text_parts).strip(),
        "latency_s": round(elapsed, 3),
        "detected_language": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "duration_s": round(float(info.duration), 3),
        "segments": seg_count,
    }


def similarity(a: str, b: str) -> float:
    """Character-level SequenceMatcher ratio. 0.0=disjoint, 1.0=identical."""
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def verdict(
    *,
    text: str,
    requested_lang: str,
    detected_lang: str,
    lang_prob: float,
    sim: float,
) -> tuple[str, str]:
    """Return (pass_fail, reason)."""
    if len(text) < 5:
        return "FAIL", f"output too short ({len(text)} chars)"
    if detected_lang != requested_lang and lang_prob < 0.5:
        return "FAIL", (
            f"detected={detected_lang} prob={lang_prob} "
            f"(requested={requested_lang})"
        )
    if sim < 0.30:
        return "FAIL", f"similarity {sim} < 0.30 floor"
    return "PASS", f"len={len(text)} sim={sim} prob={lang_prob}"


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[baseline] started {started_at}", file=sys.stderr)
    print(
        f"[baseline] loading faster-whisper:{MODEL_SIZE} "
        f"({DEVICE}, {COMPUTE_TYPE}) — first run downloads ~1.5GB",
        file=sys.stderr,
    )
    load_t0 = time.perf_counter()
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    load_elapsed = time.perf_counter() - load_t0
    print(f"[baseline] model ready in {load_elapsed:.1f}s", file=sys.stderr)

    results: list[dict[str, object]] = []
    for whisper_code, fleurs_code, prefix, display in SURVIVORS:
        print(f"\n=== {display} ({whisper_code}) ===", file=sys.stderr)
        try:
            audio_path, ground_truth = fetch_fleurs_clip(fleurs_code, prefix)
            pad_in_place(audio_path)
            run = whisper_transcribe(model, audio_path, whisper_code)
            sim = similarity(ground_truth, str(run["text"]))
            pass_fail, reason = verdict(
                text=str(run["text"]),
                requested_lang=whisper_code,
                detected_lang=str(run["detected_language"]),
                lang_prob=float(run["language_probability"]),  # type: ignore[arg-type]
                sim=sim,
            )
            results.append(
                {
                    "language": display,
                    "code": whisper_code,
                    "fleurs_code": fleurs_code,
                    "audio_path": str(audio_path.relative_to(REPO_ROOT)),
                    "ground_truth": ground_truth,
                    "transcription": run["text"],
                    "similarity": sim,
                    "latency_s": run["latency_s"],
                    "detected_language": run["detected_language"],
                    "language_probability": run["language_probability"],
                    "duration_s": run["duration_s"],
                    "verdict": pass_fail,
                    "reason": reason,
                }
            )
            print(
                f"[baseline] {display}: {pass_fail} ({reason}) "
                f"latency={run['latency_s']}s",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001 — surface every error
            err_msg = f"{type(exc).__name__}: {exc}"
            results.append(
                {
                    "language": display,
                    "code": whisper_code,
                    "fleurs_code": fleurs_code,
                    "verdict": "ERROR",
                    "reason": err_msg,
                }
            )
            print(f"[baseline] {display}: ERROR {err_msg}", file=sys.stderr)

    finished_at = datetime.now(timezone.utc).isoformat()

    # Write results markdown.
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"language_expansion_baseline_{ts}.md"
    lines: list[str] = []
    lines.append("# Language expansion Whisper FLEURS baseline\n")
    lines.append(f"Started: {started_at}\n")
    lines.append(f"Finished: {finished_at}\n")
    lines.append(
        f"Model: faster-whisper:{MODEL_SIZE} "
        f"({DEVICE}, {COMPUTE_TYPE}); load={load_elapsed:.1f}s\n"
    )
    lines.append("\n## Framing\n")
    lines.append(
        "Day 10 Session 5 expansion candidates: 8 displacement-relevant "
        "languages (uk/sw/bn/am/ti/so/ps/fr).\n\n"
        "Pre-flight drop: **Tigrinya (ti)** — not in "
        "`faster_whisper.tokenizer._LANGUAGE_CODES`. Whisper cannot "
        "transcribe ti, so it cannot pass this gate regardless.\n\n"
        "Phase 3 review drops: **Swahili (sw)**, **Amharic (am)**, "
        "**Somali (so)**, **Pashto (ps)** — translation hallucination "
        "exceeded the locked >1-failure threshold (defensibility > "
        "completeness).\n\n"
        "This baseline validates the 3 surviving languages (fr/uk/bn) "
        "against Google FLEURS ground truth via faster-whisper:medium "
        "(int8 CPU). Pass criteria: output ≥5 chars; detected language "
        "matches requested OR low-confidence detection; "
        "character-level similarity ratio ≥0.30.\n"
    )
    lines.append("\n## Per-language results\n")
    lines.append(
        "| Lang | Verdict | Similarity | Latency | Detected lang (prob) | Notes |\n"
    )
    lines.append(
        "|------|---------|------------|---------|----------------------|-------|\n"
    )
    for r in results:
        if r.get("verdict") == "ERROR":
            lines.append(
                f"| {r['language']} ({r['code']}) | ERROR | — | — | — | "
                f"{r['reason']} |\n"
            )
        else:
            lines.append(
                f"| {r['language']} ({r['code']}) | {r['verdict']} | "
                f"{r['similarity']} | {r['latency_s']}s | "
                f"{r['detected_language']} ({r['language_probability']}) | "
                f"{r['reason']} |\n"
            )
    lines.append("\n## Transcriptions\n")
    for r in results:
        lines.append(f"\n### {r['language']} ({r['code']})\n")
        if r.get("verdict") == "ERROR":
            lines.append(f"\nERROR: {r['reason']}\n")
            continue
        lines.append(f"\n**Audio:** `{r['audio_path']}`  \n")
        lines.append(f"**Duration:** {r['duration_s']}s  \n")
        lines.append(f"**Ground truth (FLEURS):**\n\n> {r['ground_truth']}\n")
        lines.append(f"\n**Whisper transcription:**\n\n> {r['transcription']}\n")
    lines.append("\n## Devpost framing (for Day 13+ writeup, not this session)\n")
    survivors = [r for r in results if r.get("verdict") == "PASS"]
    survivor_names = ", ".join(
        f"{r['language']} ({r['code']})" for r in survivors
    )
    lines.append(
        f"\nKIN supports **{4 + len(survivors)} languages** chosen for "
        f"displacement relevance: en/es/ar/fa (full demo coverage), "
        f"{survivor_names} (validated against Whisper baseline + safety "
        f"classification).\n"
    )

    out_path.write_text("".join(lines))
    print(f"\n[baseline] wrote {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
