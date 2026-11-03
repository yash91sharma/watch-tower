"""Tests for the restart window in wt.health.rules (pure)."""

from datetime import UTC, datetime, timedelta

from wt.health.rules import RestartWindow

T0 = datetime(2026, 1, 1, tzinfo=UTC)
N = 3
M = timedelta(minutes=10)


def restarts(window: RestartWindow, times: list[timedelta]) -> None:
    for offset in times:
        window.die(T0 + offset)
        window.start(T0 + offset + timedelta(seconds=1))


def test_n_minus_1_starts_are_no_loop() -> None:
    window = RestartWindow()

    restarts(window, [timedelta(minutes=minute) for minute in range(N - 1)])

    assert window.in_loop(T0 + timedelta(minutes=3), N, M) is False


def test_n_starts_are_a_loop() -> None:
    window = RestartWindow()

    restarts(window, [timedelta(minutes=minute) for minute in range(N)])

    assert window.in_loop(T0 + timedelta(minutes=3), N, M) is True


def test_n_starts_over_more_than_m_are_no_loop() -> None:
    window = RestartWindow()

    restarts(
        window, [timedelta(minutes=0), timedelta(minutes=6), timedelta(minutes=12)]
    )

    assert window.in_loop(T0 + timedelta(minutes=12, seconds=1), N, M) is False


def test_starts_with_no_die_do_not_count() -> None:
    window = RestartWindow()

    for minute in range(N):
        window.start(T0 + timedelta(minutes=minute))

    assert window.in_loop(T0 + timedelta(minutes=3), N, M) is False


def test_two_starts_after_one_die_count_once() -> None:
    window = RestartWindow()
    window.die(T0)

    for second in range(N):
        window.start(T0 + timedelta(seconds=second))

    assert window.in_loop(T0 + timedelta(seconds=5), N, M) is False


def test_loop_ends_after_m_quiet_minutes() -> None:
    window = RestartWindow()
    restarts(window, [timedelta(minutes=minute) for minute in range(N)])
    last_start = T0 + timedelta(minutes=N - 1, seconds=1)

    assert window.quiet(last_start + M - timedelta(seconds=1), M) is False
    assert window.quiet(last_start + M, M) is True


def test_no_restarts_is_quiet() -> None:
    assert RestartWindow().quiet(T0, M) is True


def test_old_restarts_are_dropped() -> None:
    window = RestartWindow()

    restarts(window, [timedelta(minutes=minute * 20) for minute in range(50)])
    window.in_loop(T0 + timedelta(minutes=49 * 20, seconds=2), N, M)

    assert len(window.restart_times) == 1
