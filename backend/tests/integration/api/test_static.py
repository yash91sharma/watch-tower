"""Tests for the static frontend files and the SPA fallback (wt.api.static)."""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastapi import Request, Response

from wt.config import Env
from wt.main import create_app

IMMUTABLE = "public, max-age=31536000, immutable"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>WT</html>")
    (root / "sw.js").write_text("// service worker")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("not for the web")
    return root


@pytest.fixture
async def site(tmp_path: Path, static_dir: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Env(data_dir=tmp_path / "data"), workers=[], static_dir=static_dir)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://wt") as http:
            yield http


@pytest.mark.anyio
async def test_hashed_asset_has_a_long_cache(site: httpx.AsyncClient) -> None:
    response = await site.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == IMMUTABLE


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/", "/containers/app/logs", "/settings"])
async def test_spa_routes_give_index_html(site: httpx.AsyncClient, path: str) -> None:
    response = await site.get(path)

    assert response.status_code == 200
    assert response.text == "<html>WT</html>"
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.anyio
async def test_index_html_has_security_headers(site: httpx.AsyncClient) -> None:
    response = await site.get("/")

    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.anyio
async def test_service_worker_has_no_cache(site: httpx.AsyncClient) -> None:
    response = await site.get("/sw.js")

    assert response.text == "// service worker"
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
async def test_unknown_api_path_gives_json_404(
    site: httpx.AsyncClient, method: str
) -> None:
    response = await site.request(method, "/api/no-such-route")

    assert response.status_code == 404
    assert response.json()["error"] == "Not Found"


@pytest.mark.anyio
async def test_a_file_outside_the_static_dir_is_not_served(
    site: httpx.AsyncClient,
) -> None:
    response = await site.get("/..%2Fsecret.txt")

    assert "not for the web" not in response.text


@pytest.mark.anyio
async def test_post_outside_api_gives_json_404(site: httpx.AsyncClient) -> None:
    response = await site.post("/settings")

    assert response.status_code == 404
    assert response.json()["error"] == "Not Found"


@pytest.mark.anyio
async def test_no_static_dir_gives_json_404(tmp_path: Path) -> None:
    app = create_app(
        Env(data_dir=tmp_path / "data"), workers=[], static_dir=tmp_path / "missing"
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://wt") as http:
        response = await http.get("/settings")

    assert response.status_code == 404
    assert response.json()["error"] == "Not Found"


@pytest.mark.anyio
async def test_404_handler_for_another_error_type_gives_json_404(
    tmp_path: Path, static_dir: Path
) -> None:
    app = create_app(Env(data_dir=tmp_path / "data"), workers=[], static_dir=static_dir)
    handler = cast(
        Callable[[Request, Exception], Awaitable[Response]],
        app.exception_handlers[404],
    )
    request = Request({"type": "http", "method": "POST", "path": "/x", "headers": []})

    response = await handler(request, RuntimeError("not an HTTP error"))

    assert response.status_code == 404
    assert json.loads(bytes(response.body)) == {
        "error": "Not Found",
        "detail": "Not Found",
    }
