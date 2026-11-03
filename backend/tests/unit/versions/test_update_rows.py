"""Tests for the update rows of the check run (respx, clock)."""

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.clock import FakeClock
from wt.config import Env, Settings, save_settings
from wt.db.models import Container, Severity, Update
from wt.docker.client import ContainerInfo
from wt.docker.inventory import Inventory
from wt.versions.check import CheckRunner, current_update

pytestmark = pytest.mark.anyio

API = "http://github.test"
LLM = "http://llm.test"
SOURCE = "org.opencontainers.image.source"
WEB = ContainerInfo(
    "id-1",
    "web",
    "nginx:1.0",
    {SOURCE: "https://github.com/o/web"},
    "running",
    "none",
    False,
    0,
)


def release(tag: str) -> dict[str, object]:
    return {
        "tag_name": tag,
        "body": f"Notes {tag}",
        "draft": False,
        "prerelease": False,
    }


def llm_reply() -> httpx.Response:
    content = json.dumps({"severity": "normal", "summary": "New features."})
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def mock_github(latest: str = "1.2") -> None:
    respx.get(f"{API}/repos/o/web/releases/latest").mock(
        return_value=httpx.Response(
            200, json=release(latest), headers={"ETag": f'"{latest}"'}
        )
    )
    respx.get(f"{API}/repos/o/web/releases").mock(
        return_value=httpx.Response(
            200, json=[release("1.2"), release("1.1"), release("1.0")]
        )
    )


@pytest.fixture
async def setup(db_engine: Engine) -> tuple[CheckRunner, Inventory]:
    save_settings(db_engine, Settings(llm_url=LLM, llm_model="m"))
    inventory = Inventory(db_engine)
    await inventory.update(WEB)
    env = Env(data_dir=Path("."), github_api_url=API)
    return CheckRunner(db_engine, env, inventory), inventory


def updates(engine: Engine) -> list[Update]:
    with Session(engine) as session:
        return list(session.exec(select(Update)))


def current(engine: Engine) -> Update | None:
    with Session(engine) as session:
        container = session.exec(select(Container).where(Container.name == "web")).one()
        return current_update(session, container)


async def test_update_row_has_notes_severity_and_summary(
    setup: tuple[CheckRunner, Inventory], db_engine: Engine, clock: FakeClock
) -> None:
    runner, _ = setup
    with respx.mock:
        mock_github()
        respx.post(f"{LLM}/v1/chat/completions").mock(return_value=llm_reply())

        await runner.run()

    [row] = updates(db_engine)
    assert (row.from_version, row.to_version) == ("1.0", "1.2")
    assert row.release_notes == "## 1.2\n\nNotes 1.2\n\n## 1.1\n\nNotes 1.1"
    assert (row.severity, row.summary, row.notified_at) == (
        Severity.NORMAL,
        "New features.",
        None,
    )
    assert current(db_engine) == row


async def test_second_run_makes_no_new_row_and_no_llm_call(
    setup: tuple[CheckRunner, Inventory], db_engine: Engine, clock: FakeClock
) -> None:
    runner, _ = setup
    with respx.mock:
        mock_github()
        llm = respx.post(f"{LLM}/v1/chat/completions").mock(return_value=llm_reply())

        await runner.run()
        await runner.run()

    assert len(updates(db_engine)) == 1
    assert llm.call_count == 1


async def test_new_running_version_makes_new_notes_and_keeps_notified_at(
    setup: tuple[CheckRunner, Inventory], db_engine: Engine, clock: FakeClock
) -> None:
    runner, inventory = setup
    with respx.mock:
        mock_github()
        llm = respx.post(f"{LLM}/v1/chat/completions").mock(return_value=llm_reply())
        await runner.run()
        with Session(db_engine) as session:
            row = session.exec(select(Update)).one()
            row.notified_at = clock.now()
            session.add(row)
            session.commit()

        await inventory.update(replace(WEB, image="nginx:1.1"))
        await runner.run()

    [row] = updates(db_engine)
    assert (row.from_version, row.release_notes) == ("1.1", "## 1.2\n\nNotes 1.2")
    assert row.notified_at == clock.now()
    assert llm.call_count == 2


async def test_old_rows_are_not_current(
    setup: tuple[CheckRunner, Inventory], db_engine: Engine, clock: FakeClock
) -> None:
    runner, inventory = setup
    with respx.mock:
        mock_github("1.1")
        respx.post(f"{LLM}/v1/chat/completions").mock(return_value=llm_reply())
        await runner.run()
    with respx.mock:
        mock_github("1.2")
        respx.post(f"{LLM}/v1/chat/completions").mock(return_value=llm_reply())
        await runner.run()

    assert [row.to_version for row in updates(db_engine)] == ["1.1", "1.2"]
    current_row = current(db_engine)
    assert current_row is not None and current_row.to_version == "1.2"

    await inventory.update(replace(WEB, image="nginx:1.2"))
    with respx.mock:
        respx.get(f"{API}/repos/o/web/releases/latest").mock(
            return_value=httpx.Response(304)
        )
        await runner.run()

    assert current(db_engine) is None
