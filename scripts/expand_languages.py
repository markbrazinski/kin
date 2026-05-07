"""Day 10 Session 5 — translate the EN safety-rules seed list to 7 new languages.

Diagnostic-only. Untracked. Output is human-reviewed before any
src/core/safety_rules.py edit lands.

Forks scripts/translate_safety_keywords.py (Day 10 Session 2) — same Gemma
text path, same OPTIONS, same direction (English → target language). The
target list is uk/sw/bn/am/so/ps/fr (7 languages). Tigrinya (ti) was
dropped pre-flight: faster_whisper.tokenizer._LANGUAGE_CODES does not
include "ti", so it cannot pass the Phase 4 Whisper FLEURS validation
gate regardless. The remaining 7 are all in Whisper's tokenizer.

Carries a local _TARGET_NAMES map rather than depending on
core.language_matrix.LANGUAGE_NAMES, which has not yet been extended to
the new languages (that lands in Phase 5 once translations + Whisper
validation have gated which languages survive). Diagnostic scripts
should not depend on yet-to-land Core changes.

Usage: .venv/bin/python scripts/expand_languages.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import ollama
import structlog

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from integration.ollama_adapter import MODEL, OPTIONS  # noqa: E402

log = structlog.get_logger("expand_languages")

# The 9 EN seed phrases lifted verbatim from src/core/safety_rules.py
# (original Day 6 Session 1 bd9e734 list).
EN_KEYWORDS: tuple[str, ...] = (
    "kill myself",
    "end my life",
    "suicide",
    "want to die",
    "hurt myself",
    "going to hurt",
    "going to kill",
    "going to attack",
    "immediate danger",
)

# Local override — see module docstring for why this is not imported
# from core.language_matrix.
_TARGET_NAMES: dict[str, str] = {
    "uk": "Ukrainian",
    "sw": "Swahili",
    "bn": "Bengali",
    "am": "Amharic",
    "so": "Somali",
    "ps": "Pashto",
    "fr": "French",
}

TARGETS: tuple[str, ...] = tuple(_TARGET_NAMES.keys())


def build_prompt(en_phrase: str, target_lang: str) -> str:
    """English-as-source, target-language-as-output. Plain text, no JSON.

    Mirrors scripts/translate_safety_keywords.py:build_prompt verbatim
    except for the local _TARGET_NAMES lookup.
    """
    target_name = _TARGET_NAMES[target_lang]
    return (
        f"Translate the following English phrase to {target_name}. "
        f"Return only the {target_name} translation as plain text, with no "
        f"commentary, no quotation marks, no transliteration, and no "
        f"explanation. Preserve the colloquial register of the original.\n\n"
        f"English phrase: {en_phrase}"
    )


def translate_one(client: ollama.Client, en_phrase: str, target_lang: str) -> str:
    prompt = build_prompt(en_phrase, target_lang)
    response = client.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options=OPTIONS,
        think=False,
    )
    content = (
        response.message.content
        if hasattr(response, "message")
        else response.get("message", {}).get("content", "")
    )
    return str(content).strip()


def main() -> int:
    client = ollama.Client()
    results: dict[str, dict[str, str]] = {}
    errors: list[tuple[str, str, str]] = []

    total_calls = len(EN_KEYWORDS) * len(TARGETS)
    log.info("translation_started", total_calls=total_calls, model=MODEL)

    for en in EN_KEYWORDS:
        results[en] = {}
        for target in TARGETS:
            t0 = time.perf_counter()
            try:
                rendered = translate_one(client, en, target)
                elapsed = time.perf_counter() - t0
                results[en][target] = rendered
                log.info(
                    "translation_complete",
                    en=en,
                    target=target,
                    rendered=rendered,
                    latency_s=round(elapsed, 2),
                )
            except Exception as e:  # noqa: BLE001 — surface every failure
                errors.append((en, target, f"{type(e).__name__}: {e}"))
                log.error(
                    "translation_failed",
                    en=en,
                    target=target,
                    error_class=type(e).__name__,
                    error_msg=str(e),
                )

    print()
    print("=" * 100)
    print(
        f"TRANSLATION RESULTS  ({len(EN_KEYWORDS)} EN keywords × "
        f"{len(TARGETS)} targets)"
    )
    print(f"errors: {len(errors)} / {total_calls}")
    print("=" * 100)
    print()

    # Side-by-side review table — one column per target language.
    header = f"{'EN':<20}"
    for t in TARGETS:
        header += f" | {t.upper():<22}"
    print(header)
    sep = f"{'-' * 20}"
    for _ in TARGETS:
        sep += f" | {'-' * 22}"
    print(sep)
    for en in EN_KEYWORDS:
        row = f"{en:<20}"
        for t in TARGETS:
            rendered = results.get(en, {}).get(t, "<ERR>")
            # truncate for the side-by-side view; full text lives in pasteable block
            row += f" | {rendered[:22]:<22}"
        print(row)

    print()
    print("=" * 100)
    print("PASTEABLE DICT (for src/core/safety_rules.py, post-review)")
    print("=" * 100)
    print()
    for target in TARGETS:
        print(f'    "{target}": frozenset({{')
        for en in EN_KEYWORDS:
            rendered = results.get(en, {}).get(target, "")
            print(f'        "{rendered}",  # EN: {en}')
        print("    }),")

    if errors:
        print()
        print("=" * 100)
        print("ERRORS")
        print("=" * 100)
        for en, target, msg in errors:
            print(f"  {en} -> {target}: {msg}")

    return 0 if len(errors) <= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
