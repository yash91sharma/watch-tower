"""Database: SQLite engine, tables and migrations."""

from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db.engine import create_db_engine
from wt.db.migrate import upgrade
from wt.db.models import Container, Host

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


def find_container(session: Session, name: str) -> Container | None:
    """The container row of the local host with this name."""
    return session.exec(
        select(Container).where(
            Container.host_id == LOCAL_HOST_ID, Container.name == name
        )
    ).first()
