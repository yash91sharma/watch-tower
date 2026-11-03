"""Tests for update notifications after a check run (respx, clock)."""

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.clock import FakeClock
from wt.config import Env, Settings, save_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, RepoCache, Severity, Update
from wt.notify.updates import notify_updates

pytestmark = pytest.mark.anyio

NTFY = "https://ntfy.test"
ENV = Env(data_dir=Path("."))


def add_update(
    engine: Engine,
    clock: FakeClock,
    name: str,
    severity: Severity = Severity.NORMAL,
    to: str = "1.2",
) -> None:
    with Session(engine) as session:
        container = Container(
            host_id=LOCAL_HOST_ID, name=name, tag="1.0", release_source=f"o/{name}"
        )
        session.add(container)
        session.merge(
            RepoCache(repo=f"o/{name}", latest_tag="1.2", fetched_at=clock.now())
        )
        session.commit()
        assert container.id is not None
        session.add(
            Update(
                container_id=container.id,
                from_version="1.0",
                to_version=to,
                severity=severity,
                summary=f"Summary {name}",
                release_notes="notes",
            )
        )
        session.commit()


def notified(engine: Engine) -> dict[str, bool]:
    with Session(engine) as session:
        rows = session.exec(
            select(Container.name, Update.to_version, Update.notified_at).join(
                Container
            )
        )
        return {f"{name}:{to}": at is not None for name, to, at in rows}


@pytest.fixture(autouse=True)
def ntfy_settings(db_engine: Engine) -> None:
    save_settings(
        db_engine,
        Settings(ntfy_url=NTFY, ntfy_topic="wt", public_url="https://wt.test"),
    )


async def test_one_update_sends_one_message(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_update(db_engine, clock, "web")
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await notify_updates(db_engine, ENV)

    request = route.calls.last.request
    assert route.call_count == 1
    assert request.headers["Title"] == "Update: web 1.0 -> 1.2"
    assert request.headers["Click"] == "https://wt.test/containers/web"
    assert notified(db_engine) == {"web:1.2": True}


async def test_two_updates_send_one_digest(db_engine: Engine, clock: FakeClock) -> None:
    add_update(db_engine, clock, "web")
    add_update(db_engine, clock, "db", Severity.CRITICAL)
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await notify_updates(db_engine, ENV)

    request = route.calls.last.request
    assert route.call_count == 1
    assert request.headers["Title"] == "2 updates"
    assert request.headers["Priority"] == "high"
    assert notified(db_engine) == {"web:1.2": True, "db:1.2": True}


async def test_a_second_run_sends_nothing(db_engine: Engine, clock: FakeClock) -> None:
    add_update(db_engine, clock, "web")
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await notify_updates(db_engine, ENV)
        clock.advance(timedelta(hours=24).total_seconds())
        await notify_updates(db_engine, ENV)

    assert route.call_count == 1


async def test_a_failed_send_goes_out_on_the_next_run(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_update(db_engine, clock, "web")
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(
            side_effect=[httpx.Response(500), httpx.Response(200)]
        )

        await notify_updates(db_engine, ENV)
        assert notified(db_engine) == {"web:1.2": False}
        await notify_updates(db_engine, ENV)

    assert route.call_count == 2
    assert notified(db_engine) == {"web:1.2": True}


async def test_a_stale_row_is_not_sent(db_engine: Engine, clock: FakeClock) -> None:
    add_update(db_engine, clock, "web", to="1.1")
    with respx.mock(assert_all_called=False):
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await notify_updates(db_engine, ENV)

    assert not route.called
    assert notified(db_engine) == {"web:1.1": False}
