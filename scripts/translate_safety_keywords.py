"""Day 10 Session 2 — translate the EN safety-rules seed list to ES/AR/FA.

Diagnostic-only. Untracked. Output is human-reviewed before any
src/core/safety_rules.py edit lands.

NOTE on direction: OllamaAdapter.translate(text, source_lang) is contracted
source-language → English (Day 10 Session 1). Here we need the inverse —
English seed phrase → target language. Rather than pollute the production
translate() API with a second direction, this script issues its own custom
prompt directly against ollama.Client().chat(). Same Gemma model, same
think=False lock, same OPTIONS dict, but a fresh prompt body. The
production translate() path stays single-direction and easy to reason
about.

Usage: .venv/bin/python scripts/translate_safety_keywords.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import ollama
import structlog

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from core.language_matrix import LANGUAGE_NAMES  # noqa: E402
from integration.ollama_adapter import MODEL, OPTIONS  # noqa: E402

log = structlog.get_logger("translate_safety_keywords")

# The 9 EN seed phrases lifted verbatim from src/core/safety_rules.py
# (_EN_CRISIS_KEYWORDS, Day 6 Session 1 bd9e734).
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

TARGETS: tuple[str, ...] = ("es", "ar", "fa")


def build_prompt(en_phrase: str, target_lang: str) -> str:
    """English-as-source, target-language-as-output. Plain text, no JSON.

    Same shape as ollama_adapter._build_translate_prompt but inverted
    direction, kept local to this script per the docstring rationale.
    """
    target_name = LANGUAGE_NAMES[target_lang]  # type: ignore[index]
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
    content = response.message.content if hasattr(response, "message") else \
        response.get("message", {}).get("content", "")
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
            except Exception as e:  # noqa: BLE001 — we want every failure surfaced
                errors.append((en, target, f"{type(e).__name__}: {e}"))
                log.error(
                    "translation_failed",
                    en=en,
                    target=target,
                    error_class=type(e).__name__,
                    error_msg=str(e),
                )

    print()
    print("=" * 80)
    print(f"TRANSLATION RESULTS  ({len(EN_KEYWORDS)} EN keywords × {len(TARGETS)} targets)")
    print(f"errors: {len(errors)} / {total_calls}")
    print("=" * 80)
    print()

    # Side-by-side review table
    print(f"{'EN':<22} | {'ES':<28} | {'AR':<28} | {'FA':<28}")
    print(f"{'-' * 22} | {'-' * 28} | {'-' * 28} | {'-' * 28}")
    for en in EN_KEYWORDS:
        es = results.get(en, {}).get("es", "<ERR>")
        ar = results.get(en, {}).get("ar", "<ERR>")
        fa = results.get(en, {}).get("fa", "<ERR>")
        print(f"{en:<22} | {es:<28} | {ar:<28} | {fa:<28}")

    print()
    print("=" * 80)
    print("PASTEABLE DICT (for src/core/safety_rules.py, post-review)")
    print("=" * 80)
    print()
    for target in TARGETS:
        print(f'    "{target}": frozenset({{')
        for en in EN_KEYWORDS:
            rendered = results.get(en, {}).get(target, "")
            print(f'        "{rendered}",  # EN: {en}')
        print("    }),")

    if errors:
        print()
        print("=" * 80)
        print("ERRORS")
        print("=" * 80)
        for en, target, msg in errors:
            print(f"  {en} -> {target}: {msg}")

    return 0 if len(errors) <= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
