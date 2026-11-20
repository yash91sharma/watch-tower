"""Tests for the texts of the field errors (wt.api.errors.field_errors)."""

from typing import Annotated

import pytest
from pydantic import AfterValidator, BaseModel, Field, ValidationError

from wt.api.errors import field_errors


def must_be_http(value: str) -> str:
    if not value.startswith("http"):
        raise ValueError("The URL must start with http:// or https://")
    return value


class Form(BaseModel):
    hours: int = Field(default=1, ge=1, le=720)
    ratio: int = Field(default=1, gt=0, lt=10)
    url: Annotated[str, AfterValidator(must_be_http)] = "http://x"
    name: str = "x"


def messages(**values: object) -> dict[str, str]:
    with pytest.raises(ValidationError) as caught:
        Form.model_validate(values)
    return {item.field: item.message for item in field_errors(caught.value.errors())}


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"hours": 0}, "Give a number of 1 or more"),
        ({"hours": 1000}, "Give a number of 720 or less"),
        ({"hours": "abc"}, "Give a whole number"),
        ({"hours": 1.5}, "Give a whole number"),
    ],
)
def test_number_errors_have_a_short_text(
    values: dict[str, object], message: str
) -> None:
    assert messages(**values) == {"hours": message}


def test_a_number_outside_an_open_range() -> None:
    assert messages(ratio=0) == {"ratio": "Give a number more than 0"}
    assert messages(ratio=10) == {"ratio": "Give a number less than 10"}


def test_a_value_error_has_only_the_text_of_the_validator() -> None:
    assert messages(url="x") == {"url": "The URL must start with http:// or https://"}


def test_other_errors_keep_the_pydantic_text() -> None:
    assert messages(name=5) == {"name": "Input should be a valid string"}
