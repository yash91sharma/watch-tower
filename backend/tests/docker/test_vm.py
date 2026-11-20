"""Docker test: a container sees the VM in /proc (task 1.4). wt_dev is a container on the VM."""

from pathlib import Path

import pytest

from tests.docker.env import docker
from wt import clock
from wt.metrics.vm import read_vm, vm_values

pytestmark = pytest.mark.docker


def test_a_container_reads_the_memory_and_cores_of_the_vm(tmp_path: Path) -> None:
    counters = read_vm(Path("/"), tmp_path, clock.now())
    values = vm_values(None, counters)

    # docker info gives the memory and the cores of the VM (not of this container).
    assert counters.mem_total == int(docker("info", "--format", "{{.MemTotal}}"))
    assert counters.cores == int(docker("info", "--format", "{{.NCPU}}"))
    assert 0 < values.mem_used < values.mem_total
    assert 0 < counters.disk_used < counters.disk_total
    assert counters.disk_read > 0
