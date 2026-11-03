"""Migration test with data: each release dump in tests/fixtures/db/ upgrades to head."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlmodel import Session

from wt.db import LOCAL_HOST_ID, open_db
from wt.db.migrate import alembic_config
from wt.db.models import Container, Event, EventKind

DUMPS = sorted((Path(__file__).parents[2] / "fixtures" / "db").glob("*.sql"))


def row_counts(db_file: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db_file)) as conn:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        return {
            # The names come from sqlite_master, not from input.
            table: conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]  # noqa: S608
            for table in tables
        }


def check_dump(dump: str, data_dir: Path) -> None:
    """Load the dump, upgrade it to head, and check the schema and the rows."""
    data_dir.mkdir()
    db_file = data_dir / "wt.db"
    with closing(sqlite3.connect(db_file)) as conn:
        conn.executescript(dump)
    before = row_counts(db_file)

    engine = open_db(data_dir)
    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            command.check(alembic_config(conn))
        assert (
            version == ScriptDirectory.from_config(alembic_config()).get_current_head()
        )
        tables_now = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    after = row_counts(db_file)
    for table, count in before.items():
        if table in tables_now and table != "alembic_version":
            assert after[table] >= count, table


@pytest.mark.parametrize("dump", DUMPS, ids=[path.stem for path in DUMPS])
def test_release_dump_upgrades_to_head(dump: Path, tmp_path: Path) -> None:
    check_dump(dump.read_text(), tmp_path / "data")


def test_check_dump_with_a_dump_of_head(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    engine = open_db(source_dir)
    with Session(engine) as session:
        container = Container(
            host_id=LOCAL_HOST_ID, name="app", image="nginx", tag="1.27"
        )
        session.add(container)
        session.commit()
        assert container.id is not None
        session.add(
            Event(
                container_id=container.id,
                kind=EventKind.RESTART_LOOP,
                time=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
    engine.dispose()
    with closing(sqlite3.connect(source_dir / "wt.db")) as conn:
        dump = "\n".join(conn.iterdump())

    check_dump(dump, tmp_path / "target")
