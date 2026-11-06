"""The app version: the backend, uv.lock and the frontend have the same version.

A release (v* tag) sets the same version in all of them.
"""

import json
import tomllib
from pathlib import Path

REPO = Path(__file__).parents[3]


def backend_version() -> str:
    pyproject = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text())
    return pyproject["project"]["version"]


def lock_version() -> str:
    lock = tomllib.loads((REPO / "backend" / "uv.lock").read_text())
    return next(p["version"] for p in lock["package"] if p["name"] == "wt")


def frontend_version() -> str:
    return json.loads((REPO / "frontend" / "package.json").read_text())["version"]


def test_all_versions_match() -> None:
    assert backend_version() == lock_version() == frontend_version()
