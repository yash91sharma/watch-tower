"""Smoke test: makes sure that the dev container runs pytest."""

import sys


def test_python_version() -> None:
    assert sys.version_info >= (3, 14)
