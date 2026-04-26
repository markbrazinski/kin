"""Crisis keyword classifier — covers all four KIN locked languages.

Original three EN tests stay verbatim (regression guard). Day 10
Session 2 adds positive-detection coverage for ES/AR/FA plus a
non-English negative case.
"""

from core.safety_rules import SafetyResult, classify


def test_crisis_keyword_blocks_intake() -> None:
    result = classify("I want to kill myself", lang="en")
    assert isinstance(result, SafetyResult)
    assert result.is_crisis is True
    assert result.suggested_action == "block_intake"
    assert "kill myself" in result.matched_keywords
    assert result.crisis_resources_locale == "en"


def test_normal_intake_proceeds() -> None:
    result = classify("My name is David and I'm looking for my mother", lang="en")
    assert result.is_crisis is False
    assert result.suggested_action == "proceed"
    assert result.matched_keywords == []
    assert result.crisis_resources_locale is None


def test_keyword_match_is_case_insensitive() -> None:
    result = classify("I WANT TO DIE", lang="en")
    assert result.is_crisis is True
    assert result.suggested_action == "block_intake"
    assert "want to die" in result.matched_keywords


def test_classify_crisis_es_detects() -> None:
    """Spanish utterance containing an approved ES crisis keyword."""
    result = classify("No puedo más, quiero morir.", lang="es")
    assert result.is_crisis is True
    assert result.suggested_action == "block_intake"
    assert "quiero morir" in result.matched_keywords
    assert result.crisis_resources_locale == "es"


def test_classify_crisis_ar_detects() -> None:
    """Arabic utterance containing an approved AR crisis keyword."""
    result = classify("أريد أن أموت لا أستطيع المتابعة", lang="ar")
    assert result.is_crisis is True
    assert result.suggested_action == "block_intake"
    assert "أريد أن أموت" in result.matched_keywords
    assert result.crisis_resources_locale == "ar"


def test_classify_crisis_fa_detects() -> None:
    """Farsi utterance containing an approved FA crisis keyword."""
    result = classify("دیگر طاقت ندارم، خودکشی می‌کنم", lang="fa")
    assert result.is_crisis is True
    assert result.suggested_action == "block_intake"
    assert "خودکشی" in result.matched_keywords
    assert result.crisis_resources_locale == "fa"


def test_classify_normal_es_proceeds() -> None:
    """Innocuous Spanish intake utterance must not trigger a crisis path."""
    result = classify("Mi nombre es David, busco a mi madre.", lang="es")
    assert result.is_crisis is False
    assert result.suggested_action == "proceed"
    assert result.matched_keywords == []
    assert result.crisis_resources_locale is None
