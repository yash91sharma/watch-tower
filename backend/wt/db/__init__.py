"""Database: SQLite engine, tables and migrations."""

from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from wt.db.engine import create_db_engine
from wt.db.migrate import upgrade
from wt.db.models import Host

# P0 watches one host: the Docker host that WT runs on.
LOCAL_HOST_ID = 1


def open_db(data_dir: Path) -> Engine:
    """Open the DB at start: upgrade it to the newest revision and add the local host."""
    engine = create_db_engine(data_dir)
    upgrade(engine)
    with Session(engine) as session:
        if session.get(Host, LOCAL_HOST_ID) is None:
            session.add(Host(id=LOCAL_HOST_ID, name="local"))
            session.commit()
    return engine
