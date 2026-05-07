"""Prose iteration spike: drive valid TranscriptionResult JSON via the prompt alone.

Day 9 Session 1. Sessions 2 + 3 of Day 8 falsified server-side `format=`
enforcement on gemma4:e2b's audio path under `think=False` (ADR-003 lock,
non-negotiable). Both `format=<schema>` and `format='json'` produced
output byte-for-byte identical to the no-format baseline.

This spike abandons server-side enforcement and varies a single thing:
the prompt text. EN baseline is the gate: 3/3 validations against
TranscriptionResult → ship-candidate identified, expand to multilang.

Two changes vs scripts/format_string_spike.py:
  1. Prompt is a module-level PROMPT constant, not _build_prompt("en").
     Each experiment edits PROMPT in place; everything else is identical.
  2. `format=` is dropped from the chat() call. Mirrors the adapter and
     probe_multilang's call shape so a winner here transfers without
     confounding the prose variable with a confirmed-broken param.

Re-uses OllamaAdapter._preprocess, _strip_json_fences, _extract_content
by direct import — same canonical pre-inference shape as the production
path. Diagnostic only — print() is the right tool here.
"""

from __future__ import annotations

import asyncio
import base64
import sys
import tempfile
import time
from pathlib import Path

import ollama
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from core.rfl_schema import TranscriptionResult  # noqa: E402
from integration.ollama_adapter import (  # noqa: E402
    MODEL,
    OPTIONS,
    OllamaAdapter,
)

AUDIO = REPO_ROOT / "audio_samples" / "english_01.wav"
RUNS = 3

# Single-variable knob. Edit this string per experiment (E1 → E5).
# Currently set to E5: format requirement repeated at start AND end of
# the prompt, with the body unchanged from baseline. Tests whether
# bracketing the audio cue with format reminders pins the model on
# envelope shape.
PROMPT = (
    "Output valid JSON with keys 'transcription' and "
    "'english_translation'. "
    "You will receive an audio clip in English. "
    "Perform these two tasks in order. "
    "Transcribe the audio in English; provide an English "
    "translation. "
    "Do not include any other text, explanation, or commentary. "
    "Audio follows. "
    "Return your response as valid JSON with keys 'transcription' and "
    "'english_translation'."
)


async def one_run(
    client: ollama.AsyncClient, adapter: OllamaAdapter, run_index: int
) -> dict:
    print(f"\n=== Run {run_index} ===")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        padded = Path(tmp.name)
    try:
        adapter._preprocess(
            AUDIO,
            padded,
            base={"audio_path": str(AUDIO), "model": MODEL, "lang": "en"},
        )
        audio_b64 = base64.b64encode(padded.read_bytes()).decode()
    finally:
        padded.unlink(missing_ok=True)

    messages = [{"role": "user", "content": PROMPT, "images": [audio_b64]}]

    start = time.perf_counter()
    response = await client.chat(
        model=MODEL,
        messages=messages,
        options=OPTIONS,
        think=False,
    )
    latency = time.perf_counter() - start

    raw = OllamaAdapter._extract_content(response)
    record = {
        "run_index": run_index,
        "latency_seconds": latency,
        "eval_count": getattr(response, "eval_count", None),
        "done_reason": getattr(response, "done_reason", None),
        "prompt_eval_count": getattr(response, "prompt_eval_count", None),
        "prompt_eval_duration": getattr(response, "prompt_eval_duration", None),
        "load_duration": getattr(response, "load_duration", None),
        "total_duration": getattr(response, "total_duration", None),
        "eval_duration": getattr(response, "eval_duration", None),
        "raw_content": raw,
    }
    print(f"latency: {latency:.2f}s")
    print(f"eval_count={record['eval_count']} done_reason={record['done_reason']}")
    print(
        f"prompt_eval_count={record['prompt_eval_count']} "
        f"prompt_eval_duration={record['prompt_eval_duration']}"
    )
    print(
        f"load_duration={record['load_duration']} "
        f"total_duration={record['total_duration']} "
        f"eval_duration={record['eval_duration']}"
    )
    print(f"raw content:\n{raw}")

    stripped = OllamaAdapter._strip_json_fences(raw)
    try:
        result = TranscriptionResult.model_validate_json(stripped)
        record["validation_status"] = "validated"
        record["validation_error_detail"] = ""
        record["transcription_text"] = result.transcription
        record["transcription_len"] = len(result.transcription)
        print(f"VALIDATED: transcription={result.transcription[:80]!r}")
        print(f"           english_translation={result.english_translation[:80]!r}")
    except ValidationError as e:
        record["validation_status"] = "InvalidToolCall"
        record["validation_error_detail"] = str(e)
        print(f"INVALID: {e}")
    except Exception as e:
        record["validation_status"] = type(e).__name__
        record["validation_error_detail"] = str(e)
        print(f"OTHER ERROR: {type(e).__name__}: {e}")
    return record


async def main() -> int:
    if not AUDIO.exists():
        print(f"MISSING: {AUDIO}", file=sys.stderr)
        return 1

    client = ollama.AsyncClient()
    adapter = OllamaAdapter(client=ollama)
    print(f"prose-spike: model={MODEL} runs={RUNS} audio={AUDIO.name}")
    print(f"OPTIONS: {OPTIONS}")
    print(f"PROMPT:\n{PROMPT}")
    print("=" * 60)

    records = []
    for i in range(1, RUNS + 1):
        records.append(await one_run(client, adapter, i))

    validated = sum(1 for r in records if r["validation_status"] == "validated")
    print(f"\n=== SPIKE RESULT: {validated}/{RUNS} schema-validated ===")
    for r in records:
        print(
            f"  run {r['run_index']}: "
            f"{r['validation_status']} "
            f"latency={r['latency_seconds']:.2f}s "
            f"eval_count={r['eval_count']}"
        )

    # Quality gate (added Day 9 Session 1 after E1 produced 3/3 schema-valid
    # but content-degraded "who's old" hallucinations across all 3 runs).
    # An experiment ships only if schema + content both hold:
    #   - 3/3 schema-validate
    #   - every transcription >= 20 chars (EN audio is multi-sentence)
    #   - raw_contents not all byte-identical (deterministic short outputs
    #     at temp=0.1 indicate the model is gaming the schema without
    #     grounding in audio)
    MIN_TRANSCRIPTION_LEN = 20
    if validated == RUNS:
        lens = [r["transcription_len"] for r in records]
        raws = [r["raw_content"] for r in records]
        all_long_enough = all(L >= MIN_TRANSCRIPTION_LEN for L in lens)
        any_diversity = len(set(raws)) > 1
        print("\n=== QUALITY GATE ===")
        print(f"  transcription lengths: {lens} (min required: {MIN_TRANSCRIPTION_LEN})")
        print(f"  unique raw_contents: {len(set(raws))} of {RUNS}")
        if all_long_enough and any_diversity:
            print("  RESULT: PASS — schema-valid AND content-valid")
            return 0
        if not all_long_enough:
            print(
                f"  RESULT: schema-pass CONTENT-FAIL — "
                f"at least one transcription < {MIN_TRANSCRIPTION_LEN} chars"
            )
        if not any_diversity:
            print(
                "  RESULT: schema-pass CONTENT-FAIL — "
                "all 3 raw_contents byte-identical (deterministic-short signal)"
            )
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
