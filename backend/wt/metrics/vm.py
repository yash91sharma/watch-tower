"""The Docker VM values, from /proc and /sys in the WT container.

/proc/stat, meminfo, loadavg, uptime and diskstats, and /sys/block, are not per
container: a container sees the values of the VM (on OrbStack, the Linux VM). The disk
size comes from statvfs of the data dir, which is on the Docker disk. The VM network is
not here: WT has its own network namespace (the sampler adds up the containers).
"""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wt.metrics.calc import rate, share_percent

# /proc/diskstats counts in sectors of 512 bytes (for all devices).
SECTOR_BYTES = 512
# Block devices that are not disks of the VM.
NOT_DISKS = ("loop", "ram", "zram", "dm-", "nbd")


class VmReadError(Exception):
    """WT cannot read a VM file or value."""


@dataclass(frozen=True)
class VmCounters:
    """One read of the VM. CPU and disk I/O are counters: a value is the change of two reads."""

    time: datetime
    # CPU ticks of all cores: busy (not idle, not iowait) and total.
    cpu_busy: int
    cpu_total: int
    cores: int
    # Bytes.
    mem_total: int
    mem_available: int
    swap_total: int
    swap_free: int
    load_1: float
    load_5: float
    load_15: float
    uptime_seconds: float
    # Bytes read and written on all disks (counters).
    disk_read: int
    disk_write: int
    # The Docker disk (bytes).
    disk_used: int
    disk_total: int


@dataclass(frozen=True)
class VmValues:
    """The VM values at one poll. None: no value yet (first poll)."""

    # % of all cores (0-100).
    cpu_percent: float | None
    cores: int
    mem_used: int
    mem_total: int
    swap_used: int
    swap_total: int
    load_1: float
    load_5: float
    load_15: float
    uptime_seconds: float
    disk_used: int
    disk_total: int
    disk_read_bps: float | None
    disk_write_bps: float | None


def read_vm(root: Path, data_dir: Path, time: datetime) -> VmCounters:
    """Read the VM files under `root` ("/" in WT, a test dir in tests)."""
    proc = root / "proc"
    cpu_busy, cpu_total, cores = _cpu(_read(proc / "stat"))
    memory = _meminfo(_read(proc / "meminfo"))
    load = _read(proc / "loadavg").split()
    disk_read, disk_write = _disk_io(_read(proc / "diskstats"), _disks(root))
    disk = os.statvfs(data_dir)
    return VmCounters(
        time=time,
        cpu_busy=cpu_busy,
        cpu_total=cpu_total,
        cores=cores,
        mem_total=_value(memory, "MemTotal"),
        mem_available=_value(memory, "MemAvailable"),
        swap_total=_value(memory, "SwapTotal"),
        swap_free=_value(memory, "SwapFree"),
        load_1=float(load[0]),
        load_5=float(load[1]),
        load_15=float(load[2]),
        uptime_seconds=float(_read(proc / "uptime").split()[0]),
        disk_read=disk_read,
        disk_write=disk_write,
        disk_used=(disk.f_blocks - disk.f_bfree) * disk.f_frsize,
        disk_total=disk.f_blocks * disk.f_frsize,
    )


def vm_values(before: VmCounters | None, after: VmCounters) -> VmValues:
    """The values from the last read (`before`, None at the first poll) and this one."""
    cpu_percent = disk_read_bps = disk_write_bps = None
    if before is not None:
        seconds = (after.time - before.time).total_seconds()
        cpu_percent = share_percent(
            after.cpu_busy - before.cpu_busy, after.cpu_total - before.cpu_total
        )
        disk_read_bps = rate(before.disk_read, after.disk_read, seconds)
        disk_write_bps = rate(before.disk_write, after.disk_write, seconds)
    return VmValues(
        cpu_percent=cpu_percent,
        cores=after.cores,
        mem_used=after.mem_total - after.mem_available,
        mem_total=after.mem_total,
        swap_used=after.swap_total - after.swap_free,
        swap_total=after.swap_total,
        load_1=after.load_1,
        load_5=after.load_5,
        load_15=after.load_15,
        uptime_seconds=after.uptime_seconds,
        disk_used=after.disk_used,
        disk_total=after.disk_total,
        disk_read_bps=disk_read_bps,
        disk_write_bps=disk_write_bps,
    )


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError as error:
        raise VmReadError(f"Cannot read {path}: {error.strerror}") from None


def _cpu(stat: str) -> tuple[int, int, int]:
    """Busy ticks, total ticks and the number of cores, from /proc/stat."""
    lines = stat.splitlines()
    # user nice system idle iowait irq softirq steal (guest is in user already).
    ticks = [int(value) for value in lines[0].split()[1:9]]
    idle = ticks[3] + ticks[4]
    cores = sum(1 for line in lines if line.startswith("cpu") and line[3].isdigit())
    return sum(ticks) - idle, sum(ticks), cores


def _meminfo(text: str) -> dict[str, int]:
    """/proc/meminfo in bytes (the file gives kB)."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        values[name] = int(rest.split()[0]) * 1024
    return values


def _value(values: dict[str, int], name: str) -> int:
    if name not in values:
        raise VmReadError(f"/proc/meminfo has no {name}")
    return values[name]


def _disks(root: Path) -> set[str]:
    """The disks of the VM: the block devices that are not loop, RAM or mapper devices.
    Partitions are not in /sys/block, so WT does not count their bytes two times.
    """
    block = root / "sys" / "block"
    try:
        names = os.listdir(block)
    except OSError as error:
        raise VmReadError(f"Cannot read {block}: {error.strerror}") from None
    return {name for name in names if not name.startswith(NOT_DISKS)}


def _disk_io(diskstats: str, disks: set[str]) -> tuple[int, int]:
    """Bytes read and written on the disks, from /proc/diskstats."""
    read = written = 0
    for line in diskstats.splitlines():
        fields = line.split()
        if fields[2] in disks:
            read += int(fields[5]) * SECTOR_BYTES
            written += int(fields[9]) * SECTOR_BYTES
    return read, written
