"""Tests for the tables in wt.db.models."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from wt.db.models import (
    Admin,
    AuthSession,
    Container,
    Event,
    EventKind,
    Host,
    RepoCache,
    Setting,
    Severity,
    Update,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def add_container(session: Session, name: str = "app") -> Container:
    if session.get(Host, 1) is None:
        session.add(Host(id=1, name="local"))
        session.commit()
    container = Container(host_id=1, name=name)
    session.add(container)
    session.commit()
    return container


def add_twice(engine: Engine, first: SQLModel, second: SQLModel) -> None:
    """Add `first`, then check that the DB rejects `second`."""
    with Session(engine) as session:
        session.add(first)
        session.commit()
    with Session(engine) as session:
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()


def test_container_defaults(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        container = add_container(session)

        assert container.id is not None
        assert container.docker_id is None
        assert container.image is None
        assert container.tag is None
        assert container.enabled is True
        assert container.source_confirmed is False


def test_container_name_is_unique_per_host(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        add_container(session, "app")
        session.add(Container(host_id=1, name="app"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_same_container_name_on_two_hosts(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        add_container(session, "app")
        session.add(Host(id=2, name="other"))
        session.commit()
        session.add(Container(host_id=2, name="app"))
        session.commit()


def test_container_needs_a_host(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        session.add(Container(host_id=99, name="app"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_update_is_unique_per_container_and_version(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        container_id = add_container(session).id
    assert container_id is not None

    def update() -> Update:
        return Update(
            container_id=container_id,
            from_version="1.0",
            to_version="1.1",
            severity=Severity.NORMAL,
            release_notes="Fixes",
        )

    add_twice(db_engine, update(), update())


def test_primary_keys_reject_duplicates(db_engine: Engine) -> None:
    add_twice(db_engine, RepoCache(repo="a/b"), RepoCache(repo="a/b"))
    add_twice(db_engine, Setting(key="k", value=1), Setting(key="k", value=2))
    add_twice(
        db_engine,
        AuthSession(token_hash="h", created=T0, expires=T0, last_seen=T0),
        AuthSession(token_hash="h", created=T0, expires=T0, last_seen=T0),
    )


def test_times_come_back_in_utc(db_engine: Engine) -> None:
    plus_two = timezone(timedelta(hours=2))
    with Session(db_engine) as session:
        container_id = add_container(session).id
        assert container_id is not None
        session.add(
            Event(
                container_id=container_id,
                kind=EventKind.BECAME_UNHEALTHY,
                time=datetime(2026, 1, 1, 2, 0, tzinfo=plus_two),
            )
        )
        session.commit()

    with Session(db_engine) as session:
        event = session.exec(select(Event)).one()

    assert event.time == T0
    assert event.time.tzinfo == UTC
    assert event.kind is EventKind.BECAME_UNHEALTHY


def test_naive_time_is_rejected(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        session.add(
            AuthSession(
                token_hash="h", created=T0, expires=T0, last_seen=datetime(2026, 1, 1)
            )
        )
        with pytest.raises(Exception, match="timezone"):
            session.commit()


def test_json_values_round_trip(db_engine: Engine) -> None:
    releases = [{"tag": "v1.1", "body": "Fixes", "draft": False}]
    with Session(db_engine) as session:
        session.add(RepoCache(repo="a/b", releases=releases, fetched_at=T0))
        session.add(Setting(key="check_interval_hours", value=24))
        session.add(Admin(password_hash="hash", totp_secret="secret", last_totp_step=5))
        session.commit()

    with Session(db_engine) as session:
        cache = session.get(RepoCache, "a/b")
        setting = session.get(Setting, "check_interval_hours")

    assert cache is not None
    assert cache.releases == releases
    assert setting is not None
    assert setting.value == 24
