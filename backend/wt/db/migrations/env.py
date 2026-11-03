"""Alembic env. Runs the migrations on the connection from wt.db.migrate.

The alembic command (dev only) has no connection. Then env.py uses the DB in WT_DATA_DIR.
"""

from alembic import context
from sqlalchemy import Connection

from wt.config import Env
from wt.db.engine import create_db_engine
from wt.db.migrate import render_item
from wt.db.models import metadata


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=metadata,
        # SQLite can change a table only with a copy (batch mode).
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


connection: Connection | None = context.config.attributes.get("connection")
if connection is not None:
    run_migrations(connection)
else:  # pragma: no cover  (the alembic command; a test runs it in a subprocess)
    engine = create_db_engine(Env().data_dir)
    with engine.connect() as new_connection:
        run_migrations(new_connection)
    engine.dispose()
