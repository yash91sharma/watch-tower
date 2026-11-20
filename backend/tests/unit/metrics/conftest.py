"""Shared test data for the metrics tests: the /proc and /sys files of a VM."""

from pathlib import Path

import pytest

STAT = """cpu  100 0 50 800 50 0 0 0 0 0
cpu0 50 0 25 400 25 0 0 0 0 0
cpu1 50 0 25 400 25 0 0 0 0 0
intr 12345
"""
MEMINFO = """MemTotal:        8000000 kB
MemFree:          200000 kB
MemAvailable:    6000000 kB
SwapTotal:       4000000 kB
SwapFree:        3000000 kB
"""
# vda and vdb are disks. vda1 is a partition (not in /sys/block). The others are not real disks.
DISKSTATS = """ 254       0 vda 10 0 100 0 20 0 200 0 0 0 0 0 0 0 0 0 0
 254       1 vda1 10 0 100 0 20 0 200 0 0 0 0 0 0 0 0 0 0
 254      16 vdb 1 0 10 0 2 0 20 0 0 0 0 0 0 0 0 0 0
   7       0 loop0 5 0 5000 0 0 0 0 0 0 0 0 0 0 0 0 0 0
   1       0 ram0 5 0 5000 0 0 0 0 0 0 0 0 0 0 0 0 0 0
  43       0 nbd0 5 0 5000 0 0 0 0 0 0 0 0 0 0 0 0 0 0
 253       0 dm-0 5 0 5000 0 0 0 0 0 0 0 0 0 0 0 0 0 0
 252       0 zram0 5 0 5000 0 0 0 0 0 0 0 0 0 0 0 0 0 0
"""
BLOCK_DEVICES = ["vda", "vdb", "loop0", "ram0", "nbd0", "dm-0", "zram0"]


@pytest.fixture
def vm_root(tmp_path: Path) -> Path:
    """A root dir with the /proc and /sys files of a VM with 2 cores."""
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "stat").write_text(STAT)
    (proc / "meminfo").write_text(MEMINFO)
    (proc / "loadavg").write_text("0.52 0.40 0.35 1/760 34299\n")
    (proc / "uptime").write_text("3700.50 7000.00\n")
    (proc / "diskstats").write_text(DISKSTATS)
    for name in BLOCK_DEVICES:
        (tmp_path / "sys" / "block" / name).mkdir(parents=True)
    return tmp_path


def write_cpu(root: Path, busy: int, idle: int) -> None:
    """Set the CPU ticks of all cores in /proc/stat (2 cores)."""
    (root / "proc" / "stat").write_text(
        f"cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 0 0 0 0 0 0 0 0 0 0\n"
        "cpu1 0 0 0 0 0 0 0 0 0 0\n"
    )
