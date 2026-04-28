"""Invariant tests for SystemClock — real Clock adapter over stdlib."""

import time
from datetime import datetime

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


def test_now_returns_tz_aware_utc_and_advances() -> None:
    first = SYSTEM_CLOCK.now()
    second = SYSTEM_CLOCK.now()
    assert isinstance(first, datetime)
    assert first.tzinfo is not None
    assert first.utcoffset() is not None
    assert first.utcoffset().total_seconds() == 0
    assert second >= first


@pytest.mark.asyncio
async def test_sleep_elapses_real_time() -> None:
    start = time.monotonic()
    await SYSTEM_CLOCK.sleep(0.01)
    elapsed = time.monotonic() - start
    assert 0.005 <= elapsed <= 0.5
