"""Tests for wt.db.open_db (DB start)."""

from pathlib import Path

from sqlmodel import Session, select

from wt.db import LOCAL_HOST_ID, open_db
from wt.db.models import Host


def hosts(data_dir: Path) -> list[tuple[int | None, str]]:
    engine = open_db(data_dir)
    try:
        with Session(engine) as session:
            return [(host.id, host.name) for host in session.exec(select(Host))]
    finally:
        engine.dispose()


def test_first_start_adds_the_local_host(tmp_path: Path) -> None:
    assert hosts(tmp_path) == [(LOCAL_HOST_ID, "local")]


def test_two_starts_give_one_host_row(tmp_path: Path) -> None:
    hosts(tmp_path)

    assert hosts(tmp_path) == [(1, "local")]
