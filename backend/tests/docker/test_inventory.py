"""Docker test: inventory of the real test containers (task 6.4)."""

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from tests.docker.env import PROJECT, PROXY_URL
from wt.db.models import Container
from wt.docker.client import DockerClient
from wt.docker.inventory import Inventory

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


async def test_inventory_of_the_test_containers(
    docker_env: dict[str, str], db_engine: Engine
) -> None:
    client = DockerClient(PROXY_URL.replace("http://", "tcp://"))
    inventory = Inventory(db_engine)
    try:
        await inventory.sync_all(client)
    finally:
        await client.close()

    with Session(db_engine) as session:
        saved = {row.name: row for row in session.exec(select(Container))}
    assert saved["wt_test_healthy"].compose_project == PROJECT
    assert saved["wt_test_tty"].compose_project is None
    assert saved["wt_test_excluded"].enabled is False
    assert saved["wt_test_socket_proxy"].enabled is False
    assert saved["wt_test_versioned"].release_source == "wt-test/versioned"
    assert (saved["wt_test_latest"].image, saved["wt_test_latest"].tag) == (
        "wt_test/app",
        "latest",
    )
    assert inventory.get("wt_test_healthy") is not None
    assert inventory.get("wt_test_excluded") is None
