"""Tests for wt.db.find_container."""

from sqlalchemy import Engine
from sqlmodel import Session

from wt.db import LOCAL_HOST_ID, find_container
from wt.db.models import Container, Host


def test_find_container_gives_the_local_row_by_name(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        session.add(Host(id=2, name="other"))
        session.commit()
        session.add(Container(host_id=2, name="web", image="other"))
        session.add(Container(host_id=LOCAL_HOST_ID, name="web", image="local"))
        session.commit()

        row = find_container(session, "web")

        assert row is not None
        assert row.image == "local"


def test_find_container_gives_none_for_an_unknown_name(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        assert find_container(session, "nothing") is None
