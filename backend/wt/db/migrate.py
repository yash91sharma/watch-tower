"""Run the Alembic migrations. WT runs `upgrade` at start.

Make a new migration in wt_dev after a change to wt/db/models.py:
    WT_DATA_DIR=/tmp/wt-alembic uv run alembic upgrade head
    WT_DATA_DIR=/tmp/wt-alembic uv run alembic revision --autogenerate -m "<what changed>"
    uv run ruff format wt/db/migrations
"""

from pathlib import Path
from typing import Any, Literal

from alembic import command
from alembic.autogenerate.api import AutogenContext
from alembic.config import Config
from sqlalchemy import Connection, Engine
from sqlmodel.sql.sqltypes import AutoString

from wt.db.models import UTCDateTime

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(connection: Connection | None = None) -> Config:
    """Give the Alembic config. With a connection, Alembic uses it (see env.py)."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    return config


def upgrade(engine: Engine) -> None:
    """Upgrade the DB to the newest revision."""
    with engine.connect() as connection:
        # SQLite changes a table with a copy, so foreign keys must be off.
        # The pragma has no effect inside a transaction, so set it first.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        with connection.begin():
            command.upgrade(alembic_config(connection), "head")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()


def render_item(
    type_: str, obj: Any, autogen_context: AutogenContext
) -> str | Literal[False]:
    """Write plain SQLAlchemy types in new migrations, so that they do not import app code."""
    if type_ == "type" and isinstance(obj, AutoString):
        return "sa.String()"
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False
