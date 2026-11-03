"""Tests for wt.auth.setup_token."""

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from wt.auth.setup_token import SetupToken
from wt.db.models import Admin


def add_admin(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Admin(password_hash="hash", totp_secret="secret", last_totp_step=1))
        session.commit()


def test_no_admin_makes_a_token_and_logs_it_once(
    db_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    token = SetupToken.at_start(db_engine)

    assert token.value is not None
    assert len(token.value) >= 43  # 32 bytes, base64
    token.check(token.value)
    token.check("wrong")
    assert caplog.text.count(token.value) == 1


def test_token_stays_the_same_until_use(db_engine: Engine) -> None:
    token = SetupToken.at_start(db_engine)
    value = token.value
    assert value is not None

    assert token.check(value) is True
    assert token.check(value) is True
    assert token.value == value


def test_wrong_token_fails(db_engine: Engine) -> None:
    token = SetupToken.at_start(db_engine)

    assert token.check("wrong") is False
    assert token.check("") is False


def test_token_fails_after_use(db_engine: Engine) -> None:
    token = SetupToken.at_start(db_engine)
    value = token.value
    assert value is not None

    token.use()

    assert token.value is None
    assert token.check(value) is False


def test_with_an_admin_there_is_no_token(
    db_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    add_admin(db_engine)

    token = SetupToken.at_start(db_engine)

    assert token.value is None
    assert token.check("") is False
    assert "setup token" not in caplog.text.lower()
