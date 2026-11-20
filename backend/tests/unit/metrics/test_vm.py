"""Tests for wt.metrics.vm (read the Docker VM values from /proc and /sys)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.metrics.conftest import BLOCK_DEVICES
from wt.metrics.vm import VmCounters, VmReadError, VmValues, read_vm, vm_values

T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def test_read_vm(vm_root: Path, tmp_path: Path) -> None:
    counters = read_vm(vm_root, tmp_path, T0)

    assert replace(counters, disk_used=0, disk_total=0) == VmCounters(
        time=T0,
        # user + system. idle and iowait are not busy.
        cpu_busy=150,
        cpu_total=1000,
        cores=2,
        mem_total=8000000 * 1024,
        mem_available=6000000 * 1024,
        swap_total=4000000 * 1024,
        swap_free=3000000 * 1024,
        load_1=0.52,
        load_5=0.40,
        load_15=0.35,
        uptime_seconds=3700.5,
        # Sectors of vda and vdb only, 512 bytes each.
        disk_read=110 * 512,
        disk_write=220 * 512,
        disk_used=0,
        disk_total=0,
    )
    # statvfs of the data dir.
    assert 0 < counters.disk_used <= counters.disk_total


def test_a_missing_file_gives_a_clear_error(vm_root: Path, tmp_path: Path) -> None:
    (vm_root / "proc" / "meminfo").unlink()

    with pytest.raises(VmReadError, match="meminfo"):
        read_vm(vm_root, tmp_path, T0)


def test_a_missing_block_dir_gives_a_clear_error(vm_root: Path, tmp_path: Path) -> None:
    for name in BLOCK_DEVICES:
        (vm_root / "sys" / "block" / name).rmdir()
    (vm_root / "sys" / "block").rmdir()

    with pytest.raises(VmReadError, match="block"):
        read_vm(vm_root, tmp_path, T0)


def test_a_file_with_a_missing_value_gives_a_clear_error(
    vm_root: Path, tmp_path: Path
) -> None:
    (vm_root / "proc" / "meminfo").write_text("MemTotal: 8000000 kB\n")

    with pytest.raises(VmReadError, match="MemAvailable"):
        read_vm(vm_root, tmp_path, T0)


def test_vm_values_of_two_reads(vm_root: Path, tmp_path: Path) -> None:
    first = read_vm(vm_root, tmp_path, T0)
    # 10 s later: 500 more CPU ticks, 100 of them busy. 1 MB read, 2 MB written.
    second = replace(
        first,
        time=T0 + timedelta(seconds=10),
        cpu_busy=first.cpu_busy + 100,
        cpu_total=first.cpu_total + 500,
        disk_read=first.disk_read + 1_000_000,
        disk_write=first.disk_write + 2_000_000,
    )

    assert vm_values(first, second) == VmValues(
        cpu_percent=20.0,
        cores=2,
        mem_used=2000000 * 1024,
        mem_total=8000000 * 1024,
        swap_used=1000000 * 1024,
        swap_total=4000000 * 1024,
        load_1=0.52,
        load_5=0.40,
        load_15=0.35,
        uptime_seconds=3700.5,
        disk_used=first.disk_used,
        disk_total=first.disk_total,
        disk_read_bps=100_000.0,
        disk_write_bps=200_000.0,
    )


def test_the_first_read_has_no_cpu_and_no_disk_rates(
    vm_root: Path, tmp_path: Path
) -> None:
    values = vm_values(None, read_vm(vm_root, tmp_path, T0))

    assert values.cpu_percent is None
    assert values.disk_read_bps is None
    assert values.disk_write_bps is None
    assert values.mem_used == 2000000 * 1024
