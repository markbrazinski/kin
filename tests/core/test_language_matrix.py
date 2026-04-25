"""Tests for core.language_matrix supported-language registry."""

from core.language_matrix import (
    IMPLEMENTED_LANGS,
    LANGUAGE_NAMES,
    is_implemented,
)


def test_implemented_langs_match_session_scope() -> None:
    """IMPLEMENTED_LANGS is exactly {en, es, ar, fa} as of Day 7
    Session 2 — the full §7 Locked language set.

    Regression guard: a language disappearing from this set without
    intentional code change means someone broke the prompt-routing
    wiring for that language.
    """
    assert IMPLEMENTED_LANGS == frozenset({"en", "es", "ar", "fa"})


def test_is_implemented_matches_set_membership() -> None:
    """is_implemented mirrors IMPLEMENTED_LANGS membership exactly."""
    assert is_implemented("en") is True
    assert is_implemented("es") is True
    assert is_implemented("ar") is True
    assert is_implemented("fa") is True
    assert is_implemented("klingon") is False
    assert all(name in LANGUAGE_NAMES for name in ("en", "es", "ar", "fa"))
