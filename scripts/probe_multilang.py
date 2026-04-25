"""Multilingual transcription probe across en/es/ar/fa — Day 8 walk step.

Empirical reality check: does Gemma 4 E2B at the adapter's locked
options dict produce JSON that validates against TranscriptionResult,
per language, on real on-disk audio? Three runs per language to
surface variance the single-shot smoke probes can't see.

Replicates the canonical ollama.chat() call pattern from
src/integration/ollama_adapter.py locally (model, options, think=False,
the language-aware prompt) and re-uses the adapter's private
_preprocess() and _strip_json_fences() helpers by direct import. The
private-method use is deliberate: this script's purpose is to observe
the same pipeline production runs through, not to ship a parallel
implementation. _build_prompt is module-scope in the adapter and is
imported the same way.

Departures from existing probe house style (test_audio_smoke.py,
farsi_retest.py, run_three_tests.py): async client (mirrors the
adapter's async surface), structlog progress logging (no print()),
inline raw content in the markdown (no per-run JSON spillover).

Design (locked, per Mark's spec):
- Single ollama.chat() call per run.
- Capture raw content AND validation outcome separately.
- 3 runs per language, continue on failure.
- No per-call timeout: runaway behavior is itself a finding.
- 10-min total wall-clock budget, checked between runs.
- No new audio sourcing; if no sample for a lang, log + skip.
- Output: results/multilang_probe_{TS}.md with placeholder Findings.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import ollama
import structlog
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from core.language_matrix import LANGUAGE_NAMES, SupportedLang  # noqa: E402
from core.rfl_schema import TranscriptionResult  # noqa: E402
from integration.ollama_adapter import (  # noqa: E402
    MODEL,
    OPTIONS,
    OllamaAdapter,
    PaddingFailed,
    PaddingUnavailable,
    _build_prompt,
)

log = structlog.get_logger("probe_multilang")

DEFAULT_LANGS: tuple[SupportedLang, ...] = ("en", "es", "ar", "fa")
DEFAULT_RUNS = 3
DEFAULT_AUDIO_DIR = REPO_ROOT / "audio_samples"
RESULTS_DIR = REPO_ROOT / "results"
BUDGET_SECONDS = 600  # 10 minutes per §8 governance

LANG_FILE_PREFIX: dict[SupportedLang, str] = {
    "en": "english",
    "es": "spanish",
    "ar": "arabic",
    "fa": "farsi",
}


@dataclass
class RunRecord:
    language: SupportedLang
    audio_path: str
    run_index: int
    latency_seconds: float | None
    eval_count: int | None
    done_reason: str | None
    raw_content: str
    validation_status: str
    validation_error_detail: str
    timestamp_iso: str


@dataclass
class LangSection:
    language: SupportedLang
    audio_path: Path | None
    runs: list[RunRecord] = field(default_factory=list)
    skipped_reason: str | None = None


def resolve_audio(audio_dir: Path, lang: SupportedLang) -> Path | None:
    prefix = LANG_FILE_PREFIX[lang]
    matches = sorted(audio_dir.glob(f"{prefix}_*.wav"))
    return matches[0] if matches else None


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


async def run_one(
    adapter: OllamaAdapter,
    client: Any,
    lang: SupportedLang,
    audio_path: Path,
    run_index: int,
) -> RunRecord:
    """One probe run. Captures latency + raw + validation independently."""
    log.info(
        "probe_run_start",
        lang=lang,
        run_index=run_index,
        audio_path=str(audio_path),
    )
    timestamp_iso = datetime.now().isoformat()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        padded_path = Path(tmp.name)

    try:
        try:
            adapter._preprocess(
                audio_path,
                padded_path,
                base={"audio_path": str(audio_path), "model": MODEL, "lang": lang},
            )
        except (PaddingUnavailable, PaddingFailed) as e:
            log.warning(
                "probe_run_failed",
                lang=lang,
                run_index=run_index,
                stage="preprocess",
                error_class=type(e).__name__,
            )
            return RunRecord(
                language=lang,
                audio_path=str(audio_path),
                run_index=run_index,
                latency_seconds=None,
                eval_count=None,
                done_reason=None,
                raw_content="",
                validation_status=type(e).__name__,
                validation_error_detail=str(e),
                timestamp_iso=timestamp_iso,
            )

        audio_b64 = base64.b64encode(padded_path.read_bytes()).decode()
    finally:
        padded_path.unlink(missing_ok=True)

    prompt = _build_prompt(lang)
    messages = [{"role": "user", "content": prompt, "images": [audio_b64]}]

    start = time.perf_counter()
    try:
        response = await client.chat(
            model=MODEL,
            messages=messages,
            options=OPTIONS,
            think=False,
        )
    except Exception as e:
        latency = time.perf_counter() - start
        log.warning(
            "probe_run_failed",
            lang=lang,
            run_index=run_index,
            stage="inference",
            error_class=type(e).__name__,
            latency_s=latency,
        )
        return RunRecord(
            language=lang,
            audio_path=str(audio_path),
            run_index=run_index,
            latency_seconds=latency,
            eval_count=None,
            done_reason=None,
            raw_content="",
            validation_status=type(e).__name__,
            validation_error_detail=str(e),
            timestamp_iso=timestamp_iso,
        )

    latency = time.perf_counter() - start
    raw_content = OllamaAdapter._extract_content(response)
    eval_count = getattr(response, "eval_count", None)
    done_reason = getattr(response, "done_reason", None)

    stripped = OllamaAdapter._strip_json_fences(raw_content)
    validation_status: str
    validation_error_detail: str
    try:
        TranscriptionResult.model_validate_json(stripped)
        validation_status = "validated"
        validation_error_detail = ""
    except ValidationError as e:
        validation_status = "InvalidToolCall"
        validation_error_detail = str(e)
    except Exception as e:
        validation_status = type(e).__name__
        validation_error_detail = str(e)

    log.info(
        "probe_run_complete",
        lang=lang,
        run_index=run_index,
        latency_s=latency,
        eval_count=eval_count,
        done_reason=done_reason,
        validation_status=validation_status,
    )
    return RunRecord(
        language=lang,
        audio_path=str(audio_path),
        run_index=run_index,
        latency_seconds=latency,
        eval_count=eval_count,
        done_reason=done_reason,
        raw_content=raw_content,
        validation_status=validation_status,
        validation_error_detail=validation_error_detail,
        timestamp_iso=timestamp_iso,
    )


def render_markdown(
    sections: list[LangSection],
    *,
    langs_attempted: list[SupportedLang],
    total_runs_planned: int,
    total_wall_seconds: float,
    completion_status: str,
    started_iso: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Multilingual probe — {started_iso}")
    lines.append("")
    lines.append("## Probe metadata")
    lines.append("")
    lines.append(f"- Started: `{started_iso}`")
    lines.append(f"- Model: `{MODEL}`")
    lines.append(f"- num_predict: `{OPTIONS['num_predict']}`")
    lines.append(f"- Options: `{OPTIONS}`")
    lines.append("- think: `False` (hardcoded; ADR-003)")
    lines.append(
        f"- Languages attempted: {', '.join(f'`{lang}`' for lang in langs_attempted)}"
    )
    lines.append("- Audio files used:")
    for sec in sections:
        if sec.audio_path is not None:
            lines.append(f"    - `{sec.language}`: `{sec.audio_path.name}`")
        else:
            lines.append(f"    - `{sec.language}`: (no sample available)")
    lines.append(f"- Total runs planned: {total_runs_planned}")
    completed = sum(len(s.runs) for s in sections)
    lines.append(f"- Total runs completed: {completed}")
    lines.append(f"- Total wall-clock time: {total_wall_seconds:.2f}s")
    lines.append(f"- Completion status: **{completion_status}**")
    lines.append("")

    for sec in sections:
        lang_name = LANGUAGE_NAMES[sec.language]
        lines.append(f"## {lang_name} (`{sec.language}`)")
        lines.append("")
        if sec.audio_path is None:
            lines.append(
                f"_No sample available in `{DEFAULT_AUDIO_DIR.name}/`. "
                f"Runs skipped._"
            )
            lines.append("")
            continue
        lines.append(f"Audio: `{sec.audio_path.name}`")
        lines.append("")
        if not sec.runs:
            lines.append("_No runs completed for this language (budget exceeded "
                         "before scheduling)._")
            lines.append("")
            continue

        lines.append(
            "| Run | Latency (s) | eval_count | done_reason | "
            "validation_status | validation_error_detail | Timestamp |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for r in sec.runs:
            lat = f"{r.latency_seconds:.2f}" if r.latency_seconds is not None else "—"
            ec = str(r.eval_count) if r.eval_count is not None else "—"
            dr = r.done_reason or "—"
            err = (
                md_escape(r.validation_error_detail)
                if r.validation_error_detail
                else ""
            )
            lines.append(
                f"| {r.run_index} | {lat} | {ec} | {dr} | "
                f"{r.validation_status} | {err} | {r.timestamp_iso} |"
            )
        lines.append("")
        for r in sec.runs:
            lines.append(f"### Run {r.run_index} raw content")
            lines.append("")
            lines.append("```text")
            lines.append(r.raw_content if r.raw_content else "(empty)")
            lines.append("```")
            lines.append("")

    lines.append("## Findings")
    lines.append("")
    lines.append("_To be filled by human after reading the data above._")
    lines.append("")
    return "\n".join(lines)


def write_results(
    sections: list[LangSection],
    *,
    langs_attempted: list[SupportedLang],
    total_runs_planned: int,
    total_wall_seconds: float,
    completion_status: str,
    started_iso: str,
    started_ts: str,
) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"multilang_probe_{started_ts}.md"
    md = render_markdown(
        sections,
        langs_attempted=langs_attempted,
        total_runs_planned=total_runs_planned,
        total_wall_seconds=total_wall_seconds,
        completion_status=completion_status,
        started_iso=started_iso,
    )
    out_path.write_text(md)
    return out_path


async def main_async(args: argparse.Namespace) -> int:
    langs: list[SupportedLang] = [lang.strip() for lang in args.langs.split(",")]
    for lang in langs:
        if lang not in LANG_FILE_PREFIX:
            log.error("unknown_language_in_cli", lang=lang)
            return 2

    audio_dir: Path = args.audio_dir
    if not audio_dir.is_dir():
        log.error("audio_dir_missing", audio_dir=str(audio_dir))
        return 2

    sections: list[LangSection] = []
    for lang in langs:
        path = resolve_audio(audio_dir, lang)
        sections.append(LangSection(language=lang, audio_path=path))
        if path is None:
            log.warning("no_sample_available", lang=lang, audio_dir=str(audio_dir))

    runs_per_lang = args.runs
    total_runs_planned = sum(
        runs_per_lang for s in sections if s.audio_path is not None
    )
    started_iso = datetime.now().isoformat()
    started_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(
        "probe_started",
        langs=langs,
        runs_per_lang=runs_per_lang,
        total_runs_planned=total_runs_planned,
        audio_dir=str(audio_dir),
    )

    client = ollama.AsyncClient()
    adapter = OllamaAdapter(client=ollama)
    completion_status = "complete"
    wall_start = time.perf_counter()

    try:
        for sec in sections:
            if sec.audio_path is None:
                continue
            for run_index in range(1, runs_per_lang + 1):
                elapsed_total = time.perf_counter() - wall_start
                if elapsed_total > BUDGET_SECONDS:
                    log.warning(
                        "probe_budget_exceeded",
                        elapsed_s=elapsed_total,
                        budget_s=BUDGET_SECONDS,
                        next_lang=sec.language,
                        next_run=run_index,
                    )
                    completion_status = "aborted at budget"
                    raise _BudgetExceeded()
                record = await run_one(
                    adapter=adapter,
                    client=client,
                    lang=sec.language,
                    audio_path=sec.audio_path,
                    run_index=run_index,
                )
                sec.runs.append(record)
                if record.validation_status != "validated":
                    completion_status = (
                        "complete with failures"
                        if completion_status == "complete"
                        else completion_status
                    )
    except _BudgetExceeded:
        pass
    except KeyboardInterrupt:
        completion_status = "interrupted by user"
        log.warning("probe_interrupted")
    finally:
        wall_total = time.perf_counter() - wall_start
        out_path = write_results(
            sections,
            langs_attempted=langs,
            total_runs_planned=total_runs_planned,
            total_wall_seconds=wall_total,
            completion_status=completion_status,
            started_iso=started_iso,
            started_ts=started_ts,
        )
        log.info(
            "probe_finished",
            completion_status=completion_status,
            wall_seconds=wall_total,
            output=str(out_path),
        )

    return 0 if completion_status in ("complete", "complete with failures") else 1


class _BudgetExceeded(Exception):
    pass


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Multilingual transcription probe across en/es/ar/fa."
    )
    ap.add_argument(
        "--langs",
        default=",".join(DEFAULT_LANGS),
        help="Comma-separated subset of en,es,ar,fa (default: all four)",
    )
    ap.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="Runs per language (default: 3)",
    )
    ap.add_argument(
        "--audio-dir",
        type=Path,
        default=DEFAULT_AUDIO_DIR,
        help="Directory containing <lang>_*.wav files (default: audio_samples/)",
    )
    return ap.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
