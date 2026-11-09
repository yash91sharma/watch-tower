# schemathesis decorators have no full types.
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Contract test: schemathesis on all routes from the OpenAPI schema. No 500 errors.

The app runs with a session cookie and FakeDocker. The GitHub URL is a closed local port,
so that no test calls the real GitHub. WT_SCHEMATHESIS_EXAMPLES sets the number of
examples per route (default 10; set more for a long run).
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from hypothesis import settings

from wt.auth import sessions
from wt.config import Env
from wt.context import AppContext
from wt.db import open_db
from wt.docker.client import ContainerInfo
from wt.docker.connection import keep_connected
from wt.docker.fake import FakeDocker
from wt.main import create_app

EXAMPLES = int(os.environ.get("WT_SCHEMATHESIS_EXAMPLES", "10"))
DATA_DIR = Path(tempfile.mkdtemp(prefix="wt-contract-"))

# A new session for each call, because the logout route deletes the session.
ENGINE = open_db(DATA_DIR)

_docker = FakeDocker()
_docker.add(
    ContainerInfo("id-web", "web", "nginx:1.27", {}, "running", "healthy", False)
)


async def fake_docker_worker(ctx: AppContext) -> None:
    await keep_connected(lambda: _docker, ctx.inventory, ctx.bus, ctx.docker_state)


app = create_app(
    Env(data_dir=DATA_DIR, github_api_url="http://127.0.0.1:9"),
    workers=[fake_docker_worker],
)
schema = schemathesis.openapi.from_dict(app.openapi())
schema.app = app


@pytest.fixture(scope="module", autouse=True)
def close_engine() -> Iterator[None]:
    yield
    ENGINE.dispose()


# ntfy-test sends to the URL in the request: no test may call a random host.
@schema.exclude(path=["/api/stream", "/api/settings/ntfy-test"]).parametrize()
@settings(max_examples=EXAMPLES, deadline=None)
def test_no_server_errors(case: schemathesis.Case[Any]) -> None:
    response = case.call(cookies={sessions.COOKIE: sessions.create_session(ENGINE)})

    assert response.status_code < 500, (
        f"{case.method} {case.formatted_path}: {response.text}"
    )
