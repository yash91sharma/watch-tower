"""Tests for the `wt` command."""

import subprocess
import sys
from pathlib import Path

import pytest

from wt.cli import main

SUBCOMMANDS = ["serve", "reset-admin", "openapi"]


def test_help_lists_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in SUBCOMMANDS:
        assert name in out


@pytest.mark.parametrize("name", SUBCOMMANDS)
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
