"""Tests for core.language_matrix supported-language registry."""

from core.language_matrix import (
    IMPLEMENTED_LANGS,
    LANGUAGE_NAMES,
    is_implemented,
)


def test_implemented_langs_match_session_scope() -> None:
    """IMPLEMENTED_LANGS is exactly {en, es, ar, fa, fr, uk} after
    Day 10 Session 5 — the original §7 Locked set plus two
    expansion survivors (French, Ukrainian) that passed Whisper
    FLEURS baseline + crisis-keyword translation review.

    Regression guard: a language disappearing from this set without
    intentional code change means someone broke the prompt-routing
    wiring for that language. A language *appearing* without a
    matching safety-rules keyword set + Whisper validation evidence
    is the same kind of break.
    """
    assert IMPLEMENTED_LANGS == frozenset({"en", "es", "ar", "fa", "fr", "uk"})


def test_is_implemented_matches_set_membership() -> None:
    """is_implemented mirrors IMPLEMENTED_LANGS membership exactly."""
    assert is_implemented("en") is True
    assert is_implemented("es") is True
    assert is_implemented("ar") is True
    assert is_implemented("fa") is True
    assert is_implemented("fr") is True
    assert is_implemented("uk") is True
    assert is_implemented("klingon") is False
    assert all(
        name in LANGUAGE_NAMES for name in ("en", "es", "ar", "fa", "fr", "uk")
    )
