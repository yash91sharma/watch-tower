"""Pure calculations: from two samples of counters to percents and rates.

A counter only goes up until its container restarts. A counter that goes down, or a
first sample with no earlier sample, gives no value (None), not a wrong value.
"""

from dataclasses import dataclass
from statistics import fmean

from wt.docker.client import ContainerStats


@dataclass(frozen=True)
class ContainerValues:
    """The values of a container at one poll. None: no value yet (first poll, restart)."""

    # % of all VM cores (0-100).
    cpu_percent: float | None
    mem_used: int
    mem_limit: int
    # Bytes per second.
    net_rx_bps: float | None
    net_tx_bps: float | None
    disk_read_bps: float | None
    disk_write_bps: float | None


def share_percent(part_delta: int, total_delta: int) -> float | None:
    """The part of the total, in % (0-100). None if a delta is not valid."""
    if part_delta < 0 or total_delta <= 0:
        return None
    # The counters are not read at the same instant, so the part can be a bit larger.
    return min(part_delta / total_delta * 100, 100.0)


def cores_used(percent: float | None, cpus: int) -> float | None:
    """The number of cores that a % of all cores is."""
    return None if percent is None else percent / 100 * cpus


def memory_used(stats: ContainerStats) -> int:
    """Used memory: usage minus the inactive file cache (the same as `docker stats`)."""
    return max(stats.mem_usage - stats.mem_inactive_file, 0)


def rate(before: int, after: int, seconds: float) -> float | None:
    """The change per second. None if the counter went down or no time passed."""
    if seconds <= 0 or after < before:
        return None
    return (after - before) / seconds


def container_values(
    before: ContainerStats | None, after: ContainerStats
) -> ContainerValues:
    """The values from the last sample (`before`, None at the first poll) and this one."""
    if before is None:
        return ContainerValues(
            cpu_percent=None,
            mem_used=memory_used(after),
            mem_limit=after.mem_limit,
            net_rx_bps=None,
            net_tx_bps=None,
            disk_read_bps=None,
            disk_write_bps=None,
        )
    seconds = (after.time - before.time).total_seconds()
    return ContainerValues(
        cpu_percent=share_percent(
            after.cpu_total - before.cpu_total, after.system_cpu - before.system_cpu
        ),
        mem_used=memory_used(after),
        mem_limit=after.mem_limit,
        net_rx_bps=rate(before.net_rx, after.net_rx, seconds),
        net_tx_bps=rate(before.net_tx, after.net_tx, seconds),
        disk_read_bps=rate(before.disk_read, after.disk_read, seconds),
        disk_write_bps=rate(before.disk_write, after.disk_write, seconds),
    )


def mean(values: list[float | None]) -> float | None:
    """The average of the values that are not None. None if there are none."""
    known = [value for value in values if value is not None]
    return fmean(known) if known else None


def mean_int(values: list[int]) -> int:
    """The rounded average (for byte counts)."""
    return round(fmean(values))
