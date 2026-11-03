"""Tests for wt.auth.limit (clock)."""

from datetime import timedelta

from wt.auth.limit import LoginLimit
from wt.clock import FakeClock


def fail(limit: LoginLimit, times: int) -> None:
    for _ in range(times):
        limit.failure()


def test_four_failures_do_not_block(clock: FakeClock) -> None:
    limit = LoginLimit()

    fail(limit, 4)

    assert limit.retry_after() is None


def test_five_failures_block_for_15_minutes(clock: FakeClock) -> None:
    limit = LoginLimit()

    fail(limit, 5)

    assert limit.retry_after() == 900
    clock.advance(timedelta(minutes=14, seconds=59).total_seconds())
    assert limit.retry_after() == 1


def test_unblock_after_15_minutes_with_a_new_count(clock: FakeClock) -> None:
    limit = LoginLimit()
    fail(limit, 5)

    clock.advance(timedelta(minutes=15).total_seconds())

    assert limit.retry_after() is None
    fail(limit, 4)
    assert limit.retry_after() is None


def test_retry_after_rounds_up(clock: FakeClock) -> None:
    limit = LoginLimit()
    fail(limit, 5)

    clock.advance(899.5)

    assert limit.retry_after() == 1


def test_success_resets_the_count(clock: FakeClock) -> None:
    limit = LoginLimit()

    fail(limit, 4)
    limit.success()
    fail(limit, 4)

    assert limit.retry_after() is None


def test_reset_clears_a_block(clock: FakeClock) -> None:
    limit = LoginLimit()
    fail(limit, 5)

    limit.success()

    assert limit.retry_after() is None
