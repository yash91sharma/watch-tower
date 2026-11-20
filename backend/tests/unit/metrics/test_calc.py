"""Tests for wt.metrics.calc (container CPU %, memory and rates)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wt.docker.client import ContainerStats
from wt.metrics.calc import (
    ContainerValues,
    container_values,
    cores_used,
    memory_used,
    rate,
    share_percent,
)

T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)

FIRST = ContainerStats(
    time=T0,
    cpu_total=1_000_000_000,
    system_cpu=100_000_000_000,
    online_cpus=10,
    mem_usage=600,
    mem_inactive_file=100,
    mem_limit=1000,
    net_rx=1000,
    net_tx=2000,
    disk_read=0,
    disk_write=500,
)
# 10 s later: the container used 1 s of CPU time, all CPUs 100 s (10 cores x 10 s).
SECOND = replace(
    FIRST,
    time=T0 + timedelta(seconds=10),
    cpu_total=2_000_000_000,
    system_cpu=200_000_000_000,
    net_rx=11000,
    net_tx=2000,
    disk_read=4096,
    disk_write=1500,
)


def test_share_percent() -> None:
    assert share_percent(1, 4) == 25.0
    assert share_percent(0, 4) == 0.0


@pytest.mark.parametrize(("part", "total"), [(-1, 4), (1, 0), (1, -4)])
def test_share_percent_with_no_valid_delta_is_none(part: int, total: int) -> None:
    # A counter that goes down (restart) or a total with no change gives no value.
    assert share_percent(part, total) is None


def test_share_percent_is_never_more_than_100() -> None:
    # The two counters are not read at the same time, so the part can be a bit larger.
    assert share_percent(5, 4) == 100.0


def test_cores_used() -> None:
    assert cores_used(10.0, 10) == 1.0
    assert cores_used(None, 10) is None


def test_memory_used_does_not_count_the_inactive_file_cache() -> None:
    assert memory_used(FIRST) == 500
    assert memory_used(replace(FIRST, mem_inactive_file=900)) == 0


def test_rate() -> None:
    assert rate(1000, 11000, 10.0) == 1000.0
    assert rate(1000, 500, 10.0) is None
    assert rate(1000, 2000, 0.0) is None


def test_container_values_of_two_samples() -> None:
    assert container_values(FIRST, SECOND) == ContainerValues(
        cpu_percent=1.0,
        mem_used=500,
        mem_limit=1000,
        net_rx_bps=1000.0,
        net_tx_bps=0.0,
        disk_read_bps=409.6,
        disk_write_bps=100.0,
    )


def test_the_first_sample_has_memory_but_no_cpu_and_no_rates() -> None:
    values = container_values(None, FIRST)

    assert values == ContainerValues(
        cpu_percent=None,
        mem_used=500,
        mem_limit=1000,
        net_rx_bps=None,
        net_tx_bps=None,
        disk_read_bps=None,
        disk_write_bps=None,
    )


def test_after_a_restart_the_counters_go_down_and_give_no_values() -> None:
    restarted = replace(SECOND, cpu_total=10, net_rx=5, disk_write=0)

    values = container_values(FIRST, restarted)

    assert values.cpu_percent is None
    assert values.net_rx_bps is None
    assert values.disk_write_bps is None
    assert values.net_tx_bps == 0.0


@given(
    cpu=st.integers(min_value=0, max_value=10**15),
    system=st.integers(min_value=1, max_value=10**15),
    cpus=st.integers(min_value=1, max_value=256),
)
def test_cpu_percent_and_cores_stay_in_range(cpu: int, system: int, cpus: int) -> None:
    second = replace(
        FIRST,
        time=T0 + timedelta(seconds=1),
        cpu_total=FIRST.cpu_total + cpu,
        system_cpu=FIRST.system_cpu + system,
        online_cpus=cpus,
    )

    percent = container_values(FIRST, second).cpu_percent

    assert percent is not None
    assert 0 <= percent <= 100
    cores = cores_used(percent, cpus)
    assert cores is not None
    assert 0 <= cores <= cpus
