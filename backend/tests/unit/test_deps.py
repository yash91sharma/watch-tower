"""Smoke test: makes sure that each runtime dependency is installed."""

import importlib

import pytest

# Import names of the runtime dependencies in pyproject.toml.
RUNTIME_MODULES = [
    "fastapi",
    "uvicorn",
    "sqlmodel",
    "alembic",
    "aiodocker",
    "httpx",
    "pydantic_settings",
    "argon2",
    "pyotp",
    "segno",
]


@pytest.mark.parametrize("name", RUNTIME_MODULES)
def test_runtime_dep_imports(name: str) -> None:
    importlib.import_module(name)
