"""Tests for the error shape {error, detail} (wt.api.errors)."""

from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from wt.api.errors import (
    _http_error,  # pyright: ignore[reportPrivateUsage]
    _validation_error,  # pyright: ignore[reportPrivateUsage]
)


class Body(BaseModel):
    password: str
    count: int


def add_test_routes(app: FastAPI) -> None:
    """Test-only routes that fail in different ways."""

    async def crash() -> None:
        raise RuntimeError("secret internal detail")

    async def not_found() -> None:
        raise HTTPException(404, "No such container", headers={"X-Test": "1"})

    async def validate(body: Body) -> None:
        return None

    app.add_api_route("/api/test/crash", crash)
    app.add_api_route("/api/test/not-found", not_found)
    app.add_api_route("/api/test/validate", validate, methods=["POST"])


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    add_test_routes(app)
    # Give the 500 response to the test, do not raise the error.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://wt") as http:
        yield http


@pytest.mark.anyio
async def test_a_route_that_raises_gives_500_with_no_trace(
    test_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = await test_client.get("/api/test/crash")

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal Server Error",
        "detail": "An error occurred. See the WT log.",
    }
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert "secret internal detail" in caplog.text


@pytest.mark.anyio
async def test_http_error_shape_and_headers(test_client: httpx.AsyncClient) -> None:
    response = await test_client.get("/api/test/not-found")

    assert response.status_code == 404
    assert response.json() == {"error": "Not Found", "detail": "No such container"}
    assert response.headers["X-Test"] == "1"


@pytest.mark.anyio
async def test_unknown_method_has_the_same_shape(
    test_client: httpx.AsyncClient,
) -> None:
    response = await test_client.delete("/api/health")

    assert response.status_code == 405
    assert response.json()["error"] == "Method Not Allowed"


@pytest.mark.anyio
async def test_validation_error_has_one_entry_per_field_and_no_input(
    test_client: httpx.AsyncClient,
) -> None:
    response = await test_client.post(
        "/api/test/validate", json={"password": 12345678901234, "count": "many"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "Unprocessable Content"
    fields = [item["field"] for item in body["detail"]]
    assert fields == ["password", "count"]
    assert all(set(item) == {"field", "message"} for item in body["detail"])
    assert "12345678901234" not in response.text
    assert "many" not in response.text


@pytest.mark.anyio
async def test_bad_json_is_a_validation_error(test_client: httpx.AsyncClient) -> None:
    response = await test_client.post(
        "/api/test/validate",
        content=b"{bad",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "Unprocessable Content"


def plain_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/x", "headers": []})


@pytest.mark.anyio
@pytest.mark.parametrize("handler", [_http_error, _validation_error])
async def test_a_handler_for_another_error_type_gives_500(
    handler: Callable[[Request, Exception], Awaitable[JSONResponse]],
) -> None:
    response = await handler(plain_request(), RuntimeError("secret internal detail"))

    assert response.status_code == 500
    assert b"secret" not in response.body
