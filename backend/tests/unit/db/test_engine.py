"""Tests for the SQLite engine in wt.db.engine."""

import sqlite3
import stat
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, text
from sqlmodel import Session

from wt.db.engine import create_db_engine

MakeEngine = Callable[[Path], Engine]


@pytest.fixture
def make_engine() -> Iterator[MakeEngine]:
    """Give create_db_engine. Close all connections after the test."""
    engines: list[Engine] = []

    def make(data_dir: Path) -> Engine:
        engines.append(create_db_engine(data_dir))
        return engines[-1]

    yield make
    for engine in engines:
        engine.dispose()


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def pragmas(conn: Connection) -> tuple[str, int, int]:
    return (
        conn.execute(text("PRAGMA journal_mode")).scalar_one(),
        conn.execute(text("PRAGMA foreign_keys")).scalar_one(),
        conn.execute(text("PRAGMA busy_timeout")).scalar_one(),
    )


def test_pragmas_on_each_new_connection(
    make_engine: MakeEngine, tmp_path: Path
) -> None:
    engine = make_engine(tmp_path)

    with engine.connect() as first, engine.connect() as second:
        assert pragmas(first) == ("wal", 1, 5000)
        assert pragmas(second) == ("wal", 1, 5000)


def test_makes_the_data_dir_and_the_db_file(
    make_engine: MakeEngine, tmp_path: Path
) -> None:
    data_dir = tmp_path / "a" / "b"

    engine = make_engine(data_dir)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
        conn.execute(text("INSERT INTO t VALUES (1)"))
        conn.commit()
        # SQLite deletes the -wal file when the last connection closes.
        assert file_mode(data_dir / "wt.db-wal") == 0o600

    assert file_mode(data_dir) == 0o700
    assert file_mode(data_dir / "wt.db") == 0o600


def test_fixes_the_mode_of_an_old_db_file(
    make_engine: MakeEngine, tmp_path: Path
) -> None:
    db_file = tmp_path / "wt.db"
    db_file.touch(mode=0o644)

    make_engine(tmp_path)

    assert file_mode(db_file) == 0o600


def test_use_from_a_second_thread(make_engine: MakeEngine, tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    with Session(engine) as session:
        session.connection().execute(text("CREATE TABLE t (x INTEGER)"))
        session.commit()

    # A session in another thread works on the same DB.
    def insert_and_count() -> int:
        with Session(engine) as session:
            session.connection().execute(text("INSERT INTO t VALUES (1)"))
            session.commit()
            return (
                session.connection()
                .execute(text("SELECT count(*) FROM t"))
                .scalar_one()
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(insert_and_count).result() == 1


def raw_connection(session: Session) -> sqlite3.Connection:
    dbapi_connection = session.connection().connection.dbapi_connection
    assert isinstance(dbapi_connection, sqlite3.Connection)
    return dbapi_connection


def is_closed(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


def test_a_connection_is_closed_when_it_comes_back(
    make_engine: MakeEngine, tmp_path: Path
) -> None:
    # At shutdown, a worker thread can hold a connection while the lifespan disposes
    # the engine. An open connection that comes back later is never closed: it gives
    # a ResourceWarning at garbage collection (a flaky test failure).
    engine = make_engine(tmp_path)
    with Session(engine) as session:
        held = raw_connection(session)
        engine.dispose()
    with Session(engine) as session:
        after_dispose = raw_connection(session)

    assert is_closed(held)
    assert is_closed(after_dispose)
