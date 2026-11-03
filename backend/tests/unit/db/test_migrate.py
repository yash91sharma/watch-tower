"""Tests for the Alembic migrations in wt.db.migrations."""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.autogenerate.api import AutogenContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, Integer, inspect, text
from sqlmodel.sql.sqltypes import AutoString

from wt.db.engine import create_db_engine
from wt.db.migrate import alembic_config, render_item, upgrade
from wt.db.models import UTCDateTime, metadata


@pytest.fixture
def empty_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(tmp_path)
    yield engine
    engine.dispose()


def head() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def test_upgrade_from_empty_to_head(empty_engine: Engine) -> None:
    upgrade(empty_engine)

    tables = set(inspect(empty_engine).get_table_names())
    assert tables == set(metadata.tables) | {"alembic_version"}
    with empty_engine.connect() as conn:
        version = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert version == head()


def test_foreign_keys_are_on_after_upgrade(empty_engine: Engine) -> None:
    upgrade(empty_engine)

    with empty_engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_upgrade_twice_changes_nothing(empty_engine: Engine) -> None:
    upgrade(empty_engine)
    upgrade(empty_engine)

    with empty_engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM alembic_version")).scalar_one()
    assert count == 1


def test_alembic_check_finds_no_drift(empty_engine: Engine) -> None:
    upgrade(empty_engine)

    with empty_engine.connect() as conn:
        config = alembic_config(conn)
        command.check(config)


def test_migrations_do_not_import_app_code() -> None:
    versions = Path(ScriptDirectory.from_config(alembic_config()).versions)

    for path in versions.glob("*.py"):
        source = path.read_text()
        assert "import wt" not in source, path.name
        assert "sqlmodel" not in source, path.name


def test_downgrade_to_base_removes_all_tables(empty_engine: Engine) -> None:
    upgrade(empty_engine)

    with empty_engine.begin() as conn:
        command.downgrade(alembic_config(conn), "base")

    assert set(inspect(empty_engine).get_table_names()) == {"alembic_version"}


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        (AutoString(), "sa.String()"),
        (UTCDateTime(), "sa.DateTime()"),
        (Integer(), False),
    ],
)
def test_render_item_writes_plain_types(obj: object, expected: str | bool) -> None:
    context = cast(AutogenContext, None)

    assert render_item("type", obj, context) == expected


def test_alembic_command_upgrades_the_db_in_data_dir(tmp_path: Path) -> None:
    alembic = Path(sys.executable).with_name("alembic")
    env = {**os.environ, "WT_DATA_DIR": str(tmp_path)}

    result = subprocess.run(
        [alembic, "upgrade", "head"],
        cwd=Path(__file__).parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    engine = create_db_engine(tmp_path)
    try:
        assert "container" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
