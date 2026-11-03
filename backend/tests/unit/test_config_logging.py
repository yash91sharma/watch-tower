"""Tests for the logging setup in wt.config."""

import logging
import re
from collections.abc import Iterator

import pytest

from wt.config import Env, configure_logging

# Example: 2026-01-01T00:00:00.123Z INFO wt.example: Hello
LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z (\w+) ([\w.]+): (.*)$")


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_one_line_with_time_level_and_module(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")

    logging.getLogger("wt.example").info("Hello")

    out = capsys.readouterr().out
    match = LINE.match(out.rstrip("\n"))
    assert match is not None, out
    assert match.groups() == ("INFO", "wt.example", "Hello")


def test_level_filters_records(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("WARNING")

    logging.getLogger("wt.example").info("hidden")
    logging.getLogger("wt.example").warning("shown")

    out = capsys.readouterr().out
    assert "hidden" not in out
    assert "shown" in out


def test_newlines_stay_in_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log = logging.getLogger("wt.example")

    log.info("first\nsecond")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log.exception("failed")

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("first\\nsecond")
    assert "RuntimeError: boom" in lines[1]


def test_a_log_of_the_config_shows_no_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("WT_GITHUB_TOKEN", "s3cret-github")
    monkeypatch.setenv("WT_NTFY_TOKEN", "s3cret-ntfy")
    monkeypatch.setenv("WT_LLM_API_KEY", "s3cret-llm")
    configure_logging("DEBUG")

    env = Env()
    logging.getLogger("wt.example").info("Config: %s", env)
    logging.getLogger("wt.example").info("Config: %r", env)

    out = capsys.readouterr().out
    assert "github_token=SecretStr" in out
    assert "s3cret" not in out
