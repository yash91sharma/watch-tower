"""SQLite engine for `{WT_DATA_DIR}/wt.db`.

Use sync SQLModel sessions: `with Session(engine) as session: ...`. FastAPI runs sync
code in threads, so a connection can move to another thread (`check_same_thread=False`).
No pool (NullPool): each connection closes when it comes back. A pool keeps a connection
open when a thread gives it back after `dispose()` (for example at shutdown).
"""

from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry, NullPool

DB_FILE = "wt.db"
BUSY_TIMEOUT_MS = 5000


def create_db_engine(data_dir: Path) -> Engine:
    """Make the data dir and the DB file (mode 600) if needed. Give the engine."""
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    data_dir.chmod(0o700)
    db_file = data_dir / DB_FILE
    # SQLite gives the -wal and -shm files the same mode as the DB file.
    db_file.touch(mode=0o600, exist_ok=True)
    db_file.chmod(0o600)

    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    event.listen(engine, "connect", _set_pragmas)
    return engine


def _set_pragmas(
    dbapi_connection: SQLiteConnection, _record: ConnectionPoolEntry
) -> None:
    """Set the pragmas on each new SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    cursor.close()
