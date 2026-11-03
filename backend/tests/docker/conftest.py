"""Fixtures for the Docker tests (marker `docker`). See tests/docker/env.py."""

import pytest

from tests.docker.env import start_test_env


@pytest.fixture(scope="session")
def docker_env() -> dict[str, str]:
    """All test containers, healthy. Name -> container id."""
    return start_test_env()
