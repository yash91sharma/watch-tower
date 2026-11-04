"""Tests for the UI settings in wt.config."""

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlmodel import Session

from wt.config import Settings, load_settings, save_settings
from wt.db.models import Setting


def test_defaults_on_an_empty_db(db_engine: Engine) -> None:
    settings = load_settings(db_engine)

    assert settings == Settings(
        check_interval_hours=24,
        restart_count=3,
        restart_window_minutes=10,
        ntfy_url=None,
        ntfy_topic=None,
        llm_url=None,
        llm_model=None,
        public_url=None,
    )


def test_save_and_load(db_engine: Engine) -> None:
    settings = Settings(
        check_interval_hours=6,
        restart_count=5,
        restart_window_minutes=15,
        ntfy_url="https://ntfy.example.com/",
        ntfy_topic="wt-alerts",
        llm_url="http://ollama:11434",
        llm_model="qwen3:4b",
        public_url="https://wt.example.com",
    )

    save_settings(db_engine, settings)

    loaded = load_settings(db_engine)
    assert loaded == settings
    assert loaded.ntfy_url == "https://ntfy.example.com"


def test_save_twice_keeps_one_row_per_key(db_engine: Engine) -> None:
    save_settings(db_engine, Settings(check_interval_hours=6))
    save_settings(db_engine, Settings(check_interval_hours=8))

    assert load_settings(db_engine).check_interval_hours == 8
    with Session(db_engine) as session:
        assert session.get(Setting, "check_interval_hours") is not None


def test_unknown_keys_in_the_db_are_ignored(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        session.add(Setting(key="old_setting", value=1))
        session.commit()

    assert load_settings(db_engine) == Settings()


def test_empty_strings_mean_not_set() -> None:
    settings = Settings.model_validate(
        {"ntfy_url": "", "ntfy_topic": " ", "llm_model": ""}
    )

    assert settings.ntfy_url is None
    assert settings.ntfy_topic is None
    assert settings.llm_model is None


@pytest.mark.parametrize(
    "values",
    [
        {"check_interval_hours": 0},
        {"restart_count": 1},
        {"restart_window_minutes": 0},
        # Upper limits: a very big number does not load back from SQLite (a float).
        {"check_interval_hours": 721},
        {"restart_count": 101},
        {"restart_window_minutes": 1441},
        {"restart_count": 1.7054105166433223e21},
        {"ntfy_url": "ftp://ntfy.example.com"},
        {"llm_url": "ollama:11434"},
        {"public_url": "javascript:alert(1)"},
        {"ntfy_topic": "a/b"},
        {"ntfy_topic": "x" * 65},
        {"unknown": 1},
    ],
)
def test_bad_values_fail(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_the_upper_limits_save_and_load(db_engine: Engine) -> None:
    settings = Settings(
        check_interval_hours=720, restart_count=100, restart_window_minutes=1440
    )

    save_settings(db_engine, settings)

    assert load_settings(db_engine) == settings
