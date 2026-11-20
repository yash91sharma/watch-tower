"""One JSON shape for all errors: {"error": <HTTP status phrase>, "detail": ...}.

`detail` is a text, or for 422 a list of {field, message}. No stack trace and no input
value goes to the client (an input can be a password).
"""

import logging
from collections.abc import Mapping, Sequence
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
    return error_response(422, field_errors(exc.errors()))


async def _server_error(request: Request, exc: Exception) -> JSONResponse:
    log.error("Error in %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "An error occurred. See the WT log.")


def field_errors(errors: Sequence[Any]) -> list[FieldError]:
    """One {field, message} per Pydantic error. No input values."""
    return [_field_error(error) for error in errors]


# Short texts for the number errors of Pydantic. {limit} is the limit in the error context.
_NUMBER_TEXTS = {
    "greater_than_equal": ("ge", "Give a number of {limit} or more"),
    "less_than_equal": ("le", "Give a number of {limit} or less"),
    "greater_than": ("gt", "Give a number more than {limit}"),
    "less_than": ("lt", "Give a number less than {limit}"),
}
_WHOLE_NUMBER_TYPES = {"int_parsing", "int_from_float", "int_type"}
# Pydantic puts this before the text of a ValueError in a validator.
_VALUE_ERROR_PREFIX = "Value error, "


def _field_error(error: Any) -> FieldError:
    location = [str(part) for part in error.get("loc", ())]
    if location and location[0] in _SOURCES:
        location = location[1:]
    return FieldError(field=".".join(location), message=_message(error))


def _message(error: Any) -> str:
    """The text of one error: short for numbers, the validator text for a ValueError."""
    kind = error.get("type")
    message = str(error.get("msg", ""))
    if kind in _NUMBER_TEXTS:
        key, text = _NUMBER_TEXTS[kind]
        return text.format(limit=error["ctx"][key])
    if kind in _WHOLE_NUMBER_TYPES:
        return "Give a whole number"
    return message.removeprefix(_VALUE_ERROR_PREFIX)


def install(app: FastAPI) -> None:
    """Add the error handlers to the app."""
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _server_error)
