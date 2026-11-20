"""Tests for wt.metrics.labels (the text of the metric values for the UI)."""

import pytest

from wt.metrics.labels import (
    bytes_label,
    cpu_label,
    load_label,
    rate_label,
    uptime_label,
    used_of_label,
)

KIB, MIB, GIB = 1024, 1024**2, 1024**3


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1023 * KIB, "1023.0 KiB"),
        (MIB, "1.0 MiB"),
        (int(3.14 * GIB), "3.1 GiB"),
        (2 * 1024 * GIB, "2.0 TiB"),
        (5000 * 1024 * GIB, "5000.0 TiB"),
        (None, "-"),
    ],
)
def test_bytes_label(value: int | None, label: str) -> None:
    assert bytes_label(value) == label


def test_used_of_label_gives_the_unit_once_when_both_values_have_it() -> None:
    assert used_of_label(int(3.1 * GIB), 8 * GIB) == "3.1 / 8.0 GiB"
    assert used_of_label(100, 1000) == "100 / 1000 B"
    assert used_of_label(None, 8 * GIB) == "-"


def test_used_of_label_gives_each_unit_when_they_are_different() -> None:
    # A small container on a large VM: "0.0 / 7.8 GiB" would not help.
    assert used_of_label(int(18.4 * MIB), int(7.8 * GIB)) == "18.4 MiB / 7.8 GiB"


@pytest.mark.parametrize(
    ("value", "label"),
    [(0.0, "0 B/s"), (1536.0, "1.5 KiB/s"), (1.2 * MIB, "1.2 MiB/s"), (None, "-")],
)
def test_rate_label(value: float | None, label: str) -> None:
    assert rate_label(value) == label


@pytest.mark.parametrize(
    ("percent", "cores", "label"),
    [
        (9.09, 1.0, "9.1% (1.0 core)"),
        # Below 1 core: 2 decimals, so that a small value does not show as 0.0.
        (0.1, 0.011, "0.1% (0.01 core)"),
        (0.04, 0.0044, "0.0% (0.00 core)"),
        (8.9, 0.98, "8.9% (0.98 core)"),
        (23.4, 2.57, "23% (2.6 cores)"),
        (100.0, 11.0, "100% (11.0 cores)"),
        (None, None, "-"),
    ],
)
def test_cpu_label(percent: float | None, cores: float | None, label: str) -> None:
    assert cpu_label(percent, cores) == label


def test_load_label() -> None:
    assert load_label(0.5234, 0.4, 0.35) == "0.52 / 0.40 / 0.35"


@pytest.mark.parametrize(
    ("seconds", "label"),
    [
        (30.0, "0 min"),
        (12 * 60 + 59.0, "12 min"),
        (4 * 3600 + 12 * 60.0, "4 h 12 min"),
        (3 * 86400 + 4 * 3600 + 59 * 60.0, "3 d 4 h"),
    ],
)
def test_uptime_label(seconds: float, label: str) -> None:
    assert uptime_label(seconds) == label
