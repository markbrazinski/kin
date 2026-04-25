"""Invariant tests for FakeClock — the test fake used across the suite."""

import asyncio

import pytest

from tests.fakes.fake_clock import FakeClock


@pytest.mark.asyncio
async def test_monotonic_returns_start_until_ticked() -> None:
    clock = FakeClock(start=100.0)
    assert clock.monotonic() == 100.0
    await clock.tick(5.0)
    assert clock.monotonic() == 105.0


@pytest.mark.asyncio
async def test_sleep_suspends_until_tick_reaches_deadline() -> None:
    clock = FakeClock()
    task = asyncio.create_task(clock.sleep(10.0))
    await asyncio.sleep(0)
    assert not task.done()

    await clock.tick(5.0)
    assert not task.done()

    await clock.tick(5.0)
    assert task.done()
    await task


@pytest.mark.asyncio
async def test_multiple_sleepers_wake_in_deadline_order() -> None:
    clock = FakeClock()
    wake_order: list[float] = []

    async def sleeper(duration: float) -> None:
        await clock.sleep(duration)
        wake_order.append(duration)

    tasks = [
        asyncio.create_task(sleeper(5.0)),
        asyncio.create_task(sleeper(10.0)),
        asyncio.create_task(sleeper(1.0)),
    ]
    await asyncio.sleep(0)

    await clock.tick(10.0)
    await asyncio.gather(*tasks)

    assert wake_order == [1.0, 5.0, 10.0]


@pytest.mark.asyncio
async def test_cancelled_sleeper_removed_from_queue() -> None:
    clock = FakeClock()
    cancelled = asyncio.create_task(clock.sleep(10.0))
    await asyncio.sleep(0)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    survivor = asyncio.create_task(clock.sleep(5.0))
    await asyncio.sleep(0)
    await clock.tick(20.0)
    await survivor
    assert survivor.done()


@pytest.mark.asyncio
async def test_zero_sleep_and_zero_tick_no_op_cleanly() -> None:
    clock = FakeClock(start=42.0)
    await clock.sleep(0)
    await clock.tick(0)
    assert clock.monotonic() == 42.0


@pytest.mark.asyncio
async def test_tick_advances_now_exactly_to_target_past_all_deadlines() -> None:
    clock = FakeClock()
    sleeper = asyncio.create_task(clock.sleep(3.0))
    await asyncio.sleep(0)

    await clock.tick(10.0)
    await sleeper

    assert sleeper.done()
    assert clock.monotonic() == 10.0
