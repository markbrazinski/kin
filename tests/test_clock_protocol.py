"""Runtime check that FakeClock satisfies the core.clock.Clock Protocol."""

from core.clock import Clock
from tests.fakes.fake_clock import FakeClock


def test_fake_clock_satisfies_clock_protocol() -> None:
    assert isinstance(FakeClock(), Clock)
