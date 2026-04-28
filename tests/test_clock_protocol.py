"""Runtime check that FakeClock satisfies the core.clock.Clock Protocol."""

from datetime import datetime

from core.clock import Clock
from tests.fakes.fake_clock import FakeClock


def test_fake_clock_satisfies_clock_protocol() -> None:
    assert isinstance(FakeClock(), Clock)


def test_fake_clock_now_returns_tz_aware_datetime() -> None:
    """FakeClock satisfies the now() half of the Clock Protocol."""
    clock = FakeClock()
    result = clock.now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
