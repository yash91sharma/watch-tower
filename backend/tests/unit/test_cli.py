"""Tests for the `wt` command."""

import logging
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from wt.cli import main

SUBCOMMANDS = ["serve", "reset-admin", "openapi"]
STUBS = ["reset-admin", "openapi"]


def test_help_lists_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in SUBCOMMANDS:
        assert name in out


@pytest.mark.parametrize("name", STUBS)
def test_stub_exits_with_not_implemented(name: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main([name])

    assert exc.value.code == f"wt {name}: not implemented"


def test_no_subcommand_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err


def test_script_is_installed() -> None:
    script = Path(sys.executable).with_name("wt")

    result = subprocess.run(
        [script, "--help"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    for name in SUBCOMMANDS:
        assert name in result.stdout


@pytest.fixture
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.mark.usefixtures("restore_logging")
def test_serve_runs_uvicorn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Any, dict[str, Any]]] = []

    def fake_run(app: Any, **kwargs: Any) -> None:
        calls.append((app, kwargs))

    monkeypatch.setattr("wt.cli.uvicorn.run", fake_run)
    monkeypatch.setenv("WT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WT_LOG_LEVEL", "WARNING")

    main(["serve"])

    [(app, kwargs)] = calls
    assert isinstance(app, FastAPI)
    assert kwargs == {
        "host": "0.0.0.0",  # noqa: S104
        "port": 8000,
        "workers": 1,
        "proxy_headers": False,
        "server_header": False,
        "log_config": None,
    }
    assert logging.getLogger().level == logging.WARNING
