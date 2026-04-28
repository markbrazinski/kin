"""Supported-language registry and routing metadata for the KIN locked set + expansion.

Single source of truth for which languages KIN supports
(`SupportedLang`) versus which are wired up at the adapter/prompt
layer today (`IMPLEMENTED_LANGS`). Day 7 Session 2 completed routing
for the original four KIN languages (en/es/ar/fa). Day 10 Session 5
adds French (fr) and Ukrainian (uk) as validated-and-claimed coverage
for the Devpost Digital Equity & Inclusivity prize — both passed
Whisper FLEURS baseline + crisis-keyword translation review. Six
expansion candidates dropped on defensibility grounds (see
`results/language_expansion_baseline_20260427_003403.md`).

Pure Core: stdlib + typing only. No I/O, no model calls.
"""

from typing import Literal

# ISO-639-1 codes for KIN's supported language set.
# Original four locked per PROJECT_PLAN §7. Day 10 Session 5 adds fr/uk.
SupportedLang = Literal["en", "es", "ar", "fa", "fr", "uk"]

# Human-readable names for prompt construction. Used by the adapter
# to build language-aware prompts without hardcoding strings at the
# call site.
LANGUAGE_NAMES: dict[SupportedLang, str] = {
    "en": "English",
    "es": "Spanish",
    "ar": "Arabic",
    "fa": "Persian (Farsi)",
    "fr": "French",
    "uk": "Ukrainian",
}

# Day 7 Session 2 completed the §7 Locked set (en/es/ar/fa). Day 10
# Session 5 adds fr/uk after Whisper FLEURS baseline + translated
# crisis-keyword review. Demo continues featuring en/es/ar/fa; fr/uk
# are validated-and-claimed coverage rather than demoed.
IMPLEMENTED_LANGS: frozenset[SupportedLang] = frozenset(
    {"en", "es", "ar", "fa", "fr", "uk"}
)


def is_implemented(lang: str) -> bool:
    """Return True if `lang` is in IMPLEMENTED_LANGS.

    The adapter calls this before any inference attempt. False means
    `lang` is on the roadmap (in `SupportedLang`) but not yet wired —
    the adapter raises `UnsupportedLanguage` rather than silently
    falling through to the English path.
    """
    return lang in IMPLEMENTED_LANGS
