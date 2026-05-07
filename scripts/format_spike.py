"""Diagnostic spike: does format=schema fix the JSON-envelope failure on EN?

Day 8 Session 2. Session 1 probe (b1da424) showed 3/4 KIN languages
emit prose instead of the prompted JSON envelope. This spike tests
whether passing TranscriptionResult.model_json_schema() as `format=`
to ollama.chat() constrains the decoder enough to produce a valid
envelope without changing the prompt.

Single change vs. the Session 1 probe: + format=<schema>. Same model,
same OPTIONS, same think=False, same _preprocess pipeline, same
unmodified _build_prompt("en"). Diagnostic only — print() is fine
here per spec; this script is not production code.

Re-uses OllamaAdapter._preprocess and _build_prompt by direct import,
same private-use rationale as scripts/probe_multilang.py: this script's
purpose is to mirror the canonical pipeline production runs through.

Footgun watch: GitHub issue ollama/ollama#15260 reports that
think=False + format=<schema> can silently ignore the format constraint
on gemma4 (text-only path, Ollama 0.20.0; fix in PR #15678). We're on
0.21.0 in dev which should include the patch, but if the spike returns
prose despite format= being passed, that's the footgun present on our
setup and the session STOPs per locked decision 4.
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


async def one_run(
    client: ollama.AsyncClient, adapter: OllamaAdapter, run_index: int
) -> bool:
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
    schema = TranscriptionResult.model_json_schema()
    messages = [{"role": "user", "content": prompt, "images": [audio_b64]}]

    start = time.perf_counter()
    response = await client.chat(
        model=MODEL,
        messages=messages,
        options=OPTIONS,
        think=False,
        format=schema,
    )
    latency = time.perf_counter() - start

    raw = OllamaAdapter._extract_content(response)
    print(f"latency: {latency:.2f}s")
    print(f"eval_count: {getattr(response, 'eval_count', None)}")
    print(f"done_reason: {getattr(response, 'done_reason', None)}")
    print(f"raw content:\n{raw}")

    stripped = OllamaAdapter._strip_json_fences(raw)
    try:
        result = TranscriptionResult.model_validate_json(stripped)
        print(f"VALIDATED: transcription={result.transcription[:80]!r}")
        print(f"           english_translation={result.english_translation[:80]!r}")
        return True
    except ValidationError as e:
        print(f"INVALID: {e}")
        return False
    except Exception as e:
        print(f"OTHER ERROR: {type(e).__name__}: {e}")
        return False


async def main() -> int:
    if not AUDIO.exists():
        print(f"MISSING: {AUDIO}", file=sys.stderr)
        return 1

    client = ollama.AsyncClient()
    adapter = OllamaAdapter(client=ollama)
    print(f"format-spike: model={MODEL} runs={RUNS} audio={AUDIO.name}")
    print(f"OPTIONS: {OPTIONS}")
    print(f"schema: {TranscriptionResult.model_json_schema()}")

    results = []
    for i in range(1, RUNS + 1):
        ok = await one_run(client, adapter, i)
        results.append(ok)

    validated = sum(results)
    print(f"\n=== SPIKE RESULT: {validated}/{RUNS} validated ===")
    return 0 if validated == RUNS else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
