"""Tests for the OpenAPI schema and `wt openapi`."""

import json
from pathlib import Path

import pytest
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute

from wt.cli import main
from wt.config import Env
from wt.main import create_app


def test_wt_openapi_writes_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    main(["openapi"])

    schema = json.loads(capsys.readouterr().out)
    assert schema["info"]["title"] == "Watch Tower"
    assert "/api/containers" in schema["paths"]
    assert "/api/stream" in schema["paths"]


def test_each_api_route_has_a_typed_response() -> None:
    app = create_app(Env(data_dir=Path("/nonexistent")), workers=[])

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        typed = route.response_model is not None or route.status_code == 204
        streaming = route.response_class is StreamingResponse
        assert typed or streaming, f"{route.path} has no response model"


def test_errors_use_the_wt_error_shape() -> None:
    schema = create_app(Env(data_dir=Path("/nonexistent")), workers=[]).openapi()

    put = schema["paths"]["/api/settings"]["put"]["responses"]
    assert put["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorBody"
    )
    assert "HTTPValidationError" not in schema["components"]["schemas"]
