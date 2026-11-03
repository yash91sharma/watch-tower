"""Tests for the SQLite engine in wt.db.engine."""

import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import Connection, text
from sqlmodel import Session

from wt.db.engine import create_db_engine


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def pragmas(conn: Connection) -> tuple[str, int, int]:
    return (
        conn.execute(text("PRAGMA journal_mode")).scalar_one(),
        conn.execute(text("PRAGMA foreign_keys")).scalar_one(),
        conn.execute(text("PRAGMA busy_timeout")).scalar_one(),
    )


def test_pragmas_on_each_new_connection(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path)

    with engine.connect() as first, engine.connect() as second:
        assert pragmas(first) == ("wal", 1, 5000)
        assert pragmas(second) == ("wal", 1, 5000)


def test_makes_the_data_dir_and_the_db_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "a" / "b"

    engine = create_db_engine(data_dir)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
        conn.execute(text("INSERT INTO t VALUES (1)"))
        conn.commit()

    assert file_mode(data_dir) == 0o700
    assert file_mode(data_dir / "wt.db") == 0o600
    assert file_mode(data_dir / "wt.db-wal") == 0o600


def test_fixes_the_mode_of_an_old_db_file(tmp_path: Path) -> None:
    db_file = tmp_path / "wt.db"
    db_file.touch(mode=0o644)

    create_db_engine(tmp_path)

    assert file_mode(db_file) == 0o600


def test_use_from_a_second_thread(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path)
    with Session(engine) as session:
        session.connection().execute(text("CREATE TABLE t (x INTEGER)"))
        session.commit()

    # The pool gives the same SQLite connection to the other thread.
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
