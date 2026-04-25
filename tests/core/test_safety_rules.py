"""Day-1 anchor test #1 (partial): EN crisis keyword classifier.

Three cases prove the mechanism. Multilingual + semantic paths land
Day 7-9 per docs/test_strategy.md §8.
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
