"""Diagnostic spike: does format='json' (string mode) engage on the audio path?

Day 8 Session 3. Session 2 spike (scripts/format_spike.py +
results/format_attempt_20260425_144304.md) falsified format=<schema>
on gemma4:e2b audio path under Ollama 0.21.0 / SDK 0.6.1: 0/3 EN runs
validated, output byte-for-byte identical to Session 1's no-format
baseline. Issue ollama/ollama#15260 (think=False + format= silently
ignored) is the documented footgun.

Hypothesis under test: format='json' (string) traverses a different
server-side code path than format=<dict> — string → JSON-mode sampler;
dict → schema-mask sampler. Pre-flight ChatRequest serialization
confirms the wire payloads differ. If the JSON-mode sampler engages
where the schema-mask sampler silently drops, that's empirical
progress; pydantic validation against TranscriptionResult still
gates on the envelope shape.

Single change vs. Session 2 spike: format=<schema> → format='json'.
Plus 6 new telemetry fields per Session 3 design decision 2:
prompt_eval_count, prompt_eval_duration, load_duration, total_duration,
eval_duration, format_param_sent.

Re-uses OllamaAdapter._preprocess and _strip_json_fences by direct
import. Diagnostic only — print() is the right tool here. ADR-003
think=False lock is non-negotiable in this session.
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
    _build_prompt,
)

AUDIO = REPO_ROOT / "audio_samples" / "english_01.wav"
RUNS = 3
FORMAT_PARAM = "json"


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

    prompt = _build_prompt("en")
    messages = [{"role": "user", "content": prompt, "images": [audio_b64]}]

    start = time.perf_counter()
    response = await client.chat(
        model=MODEL,
        messages=messages,
        options=OPTIONS,
        think=False,
        format=FORMAT_PARAM,
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
        "format_param_sent": FORMAT_PARAM,
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
    print(f"format-string-spike: model={MODEL} runs={RUNS} audio={AUDIO.name}")
    print(f"OPTIONS: {OPTIONS}")
    print(f"format param sent: {FORMAT_PARAM!r}")

    records = []
    for i in range(1, RUNS + 1):
        records.append(await one_run(client, adapter, i))

    validated = sum(1 for r in records if r["validation_status"] == "validated")
    print(f"\n=== SPIKE RESULT: {validated}/{RUNS} validated ===")
    for r in records:
        print(
            f"  run {r['run_index']}: "
            f"{r['validation_status']} "
            f"latency={r['latency_seconds']:.2f}s "
            f"eval_count={r['eval_count']}"
        )
    return 0 if validated == RUNS else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
