"""One JSON shape for all errors: {"error": <HTTP status phrase>, "detail": ...}.

`detail` is a text, or for 422 a list of {field, message}. No stack trace and no input
value goes to the client (an input can be a password).
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

log = logging.getLogger(__name__)

# The first item of a validation error location: where the value came from.
_SOURCES = {"body", "query", "path", "header", "cookie"}


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    error: str
    detail: str | list[FieldError]


def error_response(
    status: int,
    detail: str | list[FieldError],
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorBody(error=HTTPStatus(status).phrase, detail=detail)
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        return await _server_error(request, exc)
    return error_response(exc.status_code, str(exc.detail), exc.headers)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await _server_error(request, exc)
    fields = [_field_error(error) for error in exc.errors()]
    return error_response(422, fields)


async def _server_error(request: Request, exc: Exception) -> JSONResponse:
    log.error("Error in %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "An error occurred. See the WT log.")


def _field_error(error: dict[str, Any]) -> FieldError:
    location = [str(part) for part in error.get("loc", ())]
    if location and location[0] in _SOURCES:
        location = location[1:]
    return FieldError(field=".".join(location), message=str(error.get("msg", "")))


def install(app: FastAPI) -> None:
    """Add the error handlers to the app."""
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _server_error)
