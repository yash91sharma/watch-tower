"""Tests for wt.docker.inventory with FakeDocker."""

from dataclasses import replace

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db.models import Container
from wt.docker.client import ContainerInfo
from wt.docker.fake import FakeDocker
from wt.docker.inventory import Inventory, LiveContainer

pytestmark = pytest.mark.anyio

SOURCE = "org.opencontainers.image.source"


def info(name: str, docker_id: str | None = None, **changes: object) -> ContainerInfo:
    base = ContainerInfo(
        id=docker_id or f"id-{name}",
        name=name,
        image="nginx:1.27",
        labels={"com.docker.compose.project": "site"},
        state="running",
        health="healthy",
        tty=False,
        restart_count=0,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def rows(engine: Engine) -> dict[str, Container]:
    with Session(engine) as session:
        return {row.name: row for row in session.exec(select(Container))}


async def test_sync_all_saves_rows_and_live_state(db_engine: Engine) -> None:
    docker = FakeDocker()
    docker.add(
        info(
            "web",
            labels={
                "com.docker.compose.project": "site",
                SOURCE: "https://github.com/nginx/nginx",
            },
        )
    )
    docker.add(info("db", image="postgres", labels={}, health="none", state="exited"))
    inventory = Inventory(db_engine)

    await inventory.sync_all(docker)

    saved = rows(db_engine)
    web, db = saved["web"], saved["db"]
    assert (web.docker_id, web.compose_project, web.image, web.tag) == (
        "id-web",
        "site",
        "nginx",
        "1.27",
    )
    assert (web.enabled, web.release_source, web.source_confirmed) == (
        True,
        "nginx/nginx",
        False,
    )
    assert (db.compose_project, db.image, db.tag, db.release_source) == (
        None,
        "postgres",
        "latest",
        None,
    )
    assert inventory.get("web") == LiveContainer("id-web", "web", "running", "healthy")
    assert inventory.get("db") == LiveContainer("id-db", "db", "exited", "none")


async def test_excluded_container_is_saved_disabled_with_no_live_state(
    db_engine: Engine,
) -> None:
    docker = FakeDocker()
    docker.add(info("secret", labels={"wt.enable": "False"}))
    inventory = Inventory(db_engine)

    await inventory.sync_all(docker)

    assert rows(db_engine)["secret"].enabled is False
    assert inventory.get("secret") is None
    assert inventory.names() == []


async def test_recreate_keeps_the_confirmed_source(db_engine: Engine) -> None:
    docker = FakeDocker()
    docker.add(info("web", labels={SOURCE: "https://github.com/a/b"}))
    inventory = Inventory(db_engine)
    await inventory.sync_all(docker)
    with Session(db_engine) as session:
        row = session.exec(select(Container)).one()
        row.release_source, row.source_confirmed = "admin/choice", True
        session.add(row)
        session.commit()

    docker.remove("id-web")
    docker.add(
        info("web", docker_id="new-id", labels={SOURCE: "https://github.com/c/d"})
    )
    await inventory.sync_all(docker)

    web = rows(db_engine)["web"]
    assert (web.docker_id, web.release_source, web.source_confirmed) == (
        "new-id",
        "admin/choice",
        True,
    )
    assert len(rows(db_engine)) == 1


async def test_label_change_updates_a_source_that_is_not_confirmed(
    db_engine: Engine,
) -> None:
    docker = FakeDocker()
    docker.add(info("web", labels={SOURCE: "https://github.com/a/b"}))
    inventory = Inventory(db_engine)
    await inventory.sync_all(docker)

    docker.add(info("web", labels={SOURCE: "https://github.com/c/d"}))
    await inventory.sync_all(docker)

    assert rows(db_engine)["web"].release_source == "c/d"


async def test_non_github_label_gives_no_source(db_engine: Engine) -> None:
    docker = FakeDocker()
    docker.add(info("web", labels={SOURCE: "https://gitlab.com/a/b"}))
    inventory = Inventory(db_engine)

    await inventory.sync_all(docker)

    assert rows(db_engine)["web"].release_source is None


async def test_digest_only_and_bad_image_give_no_tag(db_engine: Engine) -> None:
    docker = FakeDocker()
    docker.add(info("pinned", image="nginx@sha256:" + "a" * 64))
    docker.add(info("odd", image=""))
    inventory = Inventory(db_engine)

    await inventory.sync_all(docker)

    saved = rows(db_engine)
    assert (saved["pinned"].image, saved["pinned"].tag) == ("nginx", None)
    assert (saved["odd"].image, saved["odd"].tag) == (None, None)


async def test_a_container_that_is_gone_leaves_the_live_state_and_keeps_its_row(
    db_engine: Engine,
) -> None:
    docker = FakeDocker()
    docker.add(info("web"))
    inventory = Inventory(db_engine)
    await inventory.sync_all(docker)

    docker.remove("id-web")
    await inventory.sync_all(docker)

    assert inventory.get("web") is None
    assert "web" in rows(db_engine)


async def test_update_and_remove_one_container(db_engine: Engine) -> None:
    inventory = Inventory(db_engine)

    await inventory.update(info("web", health="unhealthy"))
    assert inventory.get("web") == LiveContainer(
        "id-web", "web", "running", "unhealthy"
    )

    assert inventory.remove("web", "old-id") is False
    assert inventory.get("web") is not None
    assert inventory.remove("web", "id-web") is True
    assert inventory.get("web") is None


async def test_synced_is_set_after_the_first_sync(db_engine: Engine) -> None:
    inventory = Inventory(db_engine)
    assert not inventory.synced.is_set()

    await inventory.sync_all(FakeDocker())

    assert inventory.synced.is_set()
