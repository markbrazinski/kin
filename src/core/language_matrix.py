"""Supported-language registry and routing metadata for EN / ES / AR / FA.

Single source of truth for which languages KIN supports
(`SupportedLang`) versus which are wired up at the adapter/prompt
layer today (`IMPLEMENTED_LANGS`). Day 7 Session 2 completes
routing for all four KIN languages.

Pure Core: stdlib + typing only. No I/O, no model calls.
"""

from typing import Literal

# ISO-639-1 codes for KIN's supported language set.
# Locked per PROJECT_PLAN §7: EN / ES / AR / FA.
SupportedLang = Literal["en", "es", "ar", "fa"]

# Human-readable names for prompt construction. Used by the adapter
# to build language-aware prompts without hardcoding strings at the
# call site.
LANGUAGE_NAMES: dict[SupportedLang, str] = {
    "en": "English",
    "es": "Spanish",
    "ar": "Arabic",
    "fa": "Persian (Farsi)",
}

# Day 7 Session 2 completes the §7 Locked set. All four KIN
# languages route through the adapter; per-language prompt files
# remain deferred to Day 11+ if probe data warrants tuning.
IMPLEMENTED_LANGS: frozenset[SupportedLang] = frozenset({"en", "es", "ar", "fa"})


def is_implemented(lang: str) -> bool:
    """Return True if `lang` is in IMPLEMENTED_LANGS.

    The adapter calls this before any inference attempt. False means
    `lang` is on the roadmap (in `SupportedLang`) but not yet wired —
    the adapter raises `UnsupportedLanguage` rather than silently
    falling through to the English path.
    """
    return lang in IMPLEMENTED_LANGS
