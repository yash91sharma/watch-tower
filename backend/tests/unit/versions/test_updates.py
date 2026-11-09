"""Tests for wt.versions.updates: which update rows need new notes (DB)."""

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, RepoCache, Severity, Update
from wt.versions.rules import Release
from wt.versions.updates import UpdatePlan, plan_updates

NOTES = "## 1.2\n\nNotes 1.2\n\n## 1.1\n\nNotes 1.1"


def setup_rows(engine: Engine, tag: str) -> Container:
    """A container "web" on `tag`, and the cache of its repo with latest 1.2."""
    releases = [Release(version, f"Notes {version}") for version in ("1.2", "1.1")]
    with Session(engine) as session:
        session.add(
            RepoCache(
                repo="o/web",
                latest_tag="1.2",
                releases=[asdict(item) for item in releases],
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            Container(
                host_id=LOCAL_HOST_ID, name="web", tag=tag, release_source="o/web"
            )
        )
        session.commit()
        return session.exec(select(Container)).one()


def add_update(engine: Engine, container_id: int, from_version: str) -> None:
    with Session(engine) as session:
        session.add(
            Update(
                container_id=container_id,
                from_version=from_version,
                to_version="1.2",
                severity=Severity.NORMAL,
                release_notes="old",
            )
        )
        session.commit()


def test_a_container_with_an_update_gets_a_plan(db_engine: Engine) -> None:
    row = setup_rows(db_engine, "1.0")
    assert row.id is not None

    assert plan_updates(db_engine, [row]) == [UpdatePlan(row.id, "1.0", "1.2", NOTES)]


def test_an_up_to_date_container_gets_no_plan(db_engine: Engine) -> None:
    row = setup_rows(db_engine, "1.2")

    assert plan_updates(db_engine, [row]) == []


def test_a_row_for_the_same_running_version_gets_no_plan(db_engine: Engine) -> None:
    row = setup_rows(db_engine, "1.0")
    assert row.id is not None
    add_update(db_engine, row.id, "1.0")

    assert plan_updates(db_engine, [row]) == []


def test_a_new_running_version_gets_a_new_plan(db_engine: Engine) -> None:
    row = setup_rows(db_engine, "1.1")
    assert row.id is not None
    add_update(db_engine, row.id, "1.0")

    assert plan_updates(db_engine, [row]) == [
        UpdatePlan(row.id, "1.1", "1.2", "## 1.2\n\nNotes 1.2")
    ]
