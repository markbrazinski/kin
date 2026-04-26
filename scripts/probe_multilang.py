"""Multilingual transcription probe across en/es/ar/fa — Day 10 two-model pipeline.

Empirical reality check on the post-Whisper architecture: does
Whisper ASR (faster-whisper medium int8 CPU) + Gemma 4 E2B
text-only translation produce TranscriptionResult objects that pass
Pydantic validation across all four KIN languages?

The probe drives the same `transcribe_and_translate_with_metrics`
function the demo will use, so any drift between probe and production
is structural (not a parallel implementation). 10-min wall-clock
budget, 3 runs per language, continue on per-run failure to surface
variance.

English short-circuits the Gemma call (lang=='en' in the pipeline);
gemma_latency_s is reported as 0.0 for English rows. RFL §1 of the
review note reminds us to inspect EN rows separately, not just count
overall validations.

Whisper model load time (~47s) is logged before the budget timer
starts, so a model-load delay does not eat into per-run budget.

Output: results/multilang_probe_{TS}.md, with the metadata block + a
per-language table (whisper_latency_s | gemma_latency_s |
total_latency_s | detected_lang | lang_prob | validation_status |
error | timestamp). Findings is a placeholder for the human reviewer.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import ollama
import structlog
from faster_whisper import WhisperModel

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from core.language_matrix import LANGUAGE_NAMES, SupportedLang  # noqa: E402
from integration._errors import AdapterError  # noqa: E402
from integration.ollama_adapter import MODEL, OPTIONS, OllamaAdapter  # noqa: E402
from integration.transcription_pipeline import (  # noqa: E402
    PipelineMetrics,
    transcribe_and_translate_with_metrics,
)
from integration.whisper_adapter import (  # noqa: E402
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
    WhisperAdapter,
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
    whisper_latency_s: float | None
    gemma_latency_s: float | None
    total_latency_s: float | None
    skipped_translation: bool
    transcription: str
    english_translation: str
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
    whisper: WhisperAdapter,
    ollama_adapter: OllamaAdapter,
    lang: SupportedLang,
    audio_path: Path,
    run_index: int,
) -> RunRecord:
    """One probe run. Captures whisper + gemma latencies independently."""
    log.info(
        "probe_run_start",
        lang=lang,
        run_index=run_index,
        audio_path=str(audio_path),
    )
    timestamp_iso = datetime.now().isoformat()

    try:
        result, metrics = await transcribe_and_translate_with_metrics(
            audio_path, lang, whisper=whisper, ollama=ollama_adapter
        )
    except AdapterError as e:
        log.warning(
            "probe_run_failed",
            lang=lang,
            run_index=run_index,
            error_class=type(e).__name__,
        )
        return RunRecord(
            language=lang,
            audio_path=str(audio_path),
            run_index=run_index,
            whisper_latency_s=None,
            gemma_latency_s=None,
            total_latency_s=None,
            skipped_translation=False,
            transcription="",
            english_translation="",
            validation_status=type(e).__name__,
            validation_error_detail=str(e),
            timestamp_iso=timestamp_iso,
        )
    except Exception as e:
        log.warning(
            "probe_run_failed_unexpected",
            lang=lang,
            run_index=run_index,
            error_class=type(e).__name__,
        )
        return RunRecord(
            language=lang,
            audio_path=str(audio_path),
            run_index=run_index,
            whisper_latency_s=None,
            gemma_latency_s=None,
            total_latency_s=None,
            skipped_translation=False,
            transcription="",
            english_translation="",
            validation_status=type(e).__name__,
            validation_error_detail=str(e),
            timestamp_iso=timestamp_iso,
        )

    log.info(
        "probe_run_complete",
        lang=lang,
        run_index=run_index,
        whisper_latency_s=metrics.whisper_latency_s,
        gemma_latency_s=metrics.gemma_latency_s,
        total_latency_s=metrics.total_latency_s,
        skipped_translation=metrics.skipped_translation,
    )

    return _record_from_result(
        lang=lang,
        audio_path=audio_path,
        run_index=run_index,
        result_transcription=result.transcription,
        result_english=result.english_translation,
        metrics=metrics,
        timestamp_iso=timestamp_iso,
    )


def _record_from_result(
    *,
    lang: SupportedLang,
    audio_path: Path,
    run_index: int,
    result_transcription: str,
    result_english: str,
    metrics: PipelineMetrics,
    timestamp_iso: str,
) -> RunRecord:
    return RunRecord(
        language=lang,
        audio_path=str(audio_path),
        run_index=run_index,
        whisper_latency_s=metrics.whisper_latency_s,
        gemma_latency_s=metrics.gemma_latency_s,
        total_latency_s=metrics.total_latency_s,
        skipped_translation=metrics.skipped_translation,
        transcription=result_transcription,
        english_translation=result_english,
        validation_status="validated",
        validation_error_detail="",
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
    whisper_load_seconds: float,
) -> str:
    lines: list[str] = []
    lines.append(f"# Multilingual probe — {started_iso}")
    lines.append("")
    lines.append("## Probe metadata")
    lines.append("")
    lines.append(f"- Started: `{started_iso}`")
    lines.append(
        f"- Whisper: `faster-whisper:{WHISPER_MODEL_SIZE}` "
        f"({WHISPER_DEVICE}, {WHISPER_COMPUTE_TYPE})"
    )
    lines.append(f"- Whisper model load: `{whisper_load_seconds:.2f}s`")
    lines.append(f"- Gemma: `{MODEL}`")
    lines.append(f"- Gemma options: `{OPTIONS}`")
    lines.append("- think: `False` (hardcoded; ADR-003)")
    lines.append("- English short-circuits Gemma (`gemma_latency_s == 0.0`)")
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
    validated = sum(
        1 for s in sections for r in s.runs if r.validation_status == "validated"
    )
    lines.append(f"- Total runs completed: {completed}")
    lines.append(f"- Validated runs: **{validated} / {total_runs_planned}**")
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
            lines.append(
                "_No runs completed for this language (budget exceeded "
                "before scheduling)._"
            )
            lines.append("")
            continue

        lines.append(
            "| Run | whisper_s | gemma_s | total_s | skipped_xlate | "
            "validation_status | error | Timestamp |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in sec.runs:
            ws = (
                f"{r.whisper_latency_s:.2f}"
                if r.whisper_latency_s is not None
                else "—"
            )
            gs = (
                f"{r.gemma_latency_s:.2f}"
                if r.gemma_latency_s is not None
                else "—"
            )
            ts = (
                f"{r.total_latency_s:.2f}"
                if r.total_latency_s is not None
                else "—"
            )
            err = (
                md_escape(r.validation_error_detail)
                if r.validation_error_detail
                else ""
            )
            lines.append(
                f"| {r.run_index} | {ws} | {gs} | {ts} | "
                f"{r.skipped_translation} | {r.validation_status} | {err} | "
                f"{r.timestamp_iso} |"
            )
        lines.append("")
        for r in sec.runs:
            lines.append(f"### Run {r.run_index} output")
            lines.append("")
            lines.append("```text")
            lines.append(f"transcription:        {r.transcription or '(empty)'}")
            lines.append(
                f"english_translation:  {r.english_translation or '(empty)'}"
            )
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
    whisper_load_seconds: float,
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
        whisper_load_seconds=whisper_load_seconds,
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
        "whisper_model_loading",
        size=WHISPER_MODEL_SIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )
    load_t0 = time.perf_counter()
    whisper_model = WhisperModel(
        WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
    )
    whisper_load_seconds = time.perf_counter() - load_t0
    log.info("whisper_model_ready", load_seconds=whisper_load_seconds)

    whisper_adapter = WhisperAdapter(model=whisper_model)
    # OllamaAdapter wraps a sync chat() via asyncio.to_thread; pass the sync
    # Client (ollama.Client), not AsyncClient. Mirrors all tests' stub clients.
    ollama_adapter = OllamaAdapter(client=ollama.Client())

    log.info(
        "probe_started",
        langs=langs,
        runs_per_lang=runs_per_lang,
        total_runs_planned=total_runs_planned,
        audio_dir=str(audio_dir),
    )

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
                    whisper=whisper_adapter,
                    ollama_adapter=ollama_adapter,
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
            whisper_load_seconds=whisper_load_seconds,
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
