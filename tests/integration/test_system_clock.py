"""Invariant tests for SystemClock — real Clock adapter over stdlib."""

import time

import pytest

from core.clock import Clock
from integration.system_clock import SYSTEM_CLOCK, SystemClock


def test_system_clock_satisfies_clock_protocol() -> None:
    assert isinstance(SYSTEM_CLOCK, Clock)
    assert isinstance(SystemClock(), Clock)


def test_monotonic_does_not_go_backward() -> None:
    first = SYSTEM_CLOCK.monotonic()
    second = SYSTEM_CLOCK.monotonic()
    assert second >= first


@pytest.mark.asyncio
async def test_sleep_elapses_real_time() -> None:
    start = time.monotonic()
    await SYSTEM_CLOCK.sleep(0.01)
    elapsed = time.monotonic() - start
    assert 0.005 <= elapsed <= 0.5
