"""Tests for wt.auth.sessions (clock)."""

from datetime import timedelta

from fastapi import Response
from sqlalchemy import Engine, text
from sqlmodel import Session, select

from wt.auth import sessions
from wt.clock import FakeClock
from wt.db.models import AuthSession


def test_cookie_flags() -> None:
    response = Response()

    sessions.set_cookie(response, "tok")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("wt_session=tok;")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=2592000" in cookie


def test_clear_cookie() -> None:
    response = Response()

    sessions.clear_cookie(response)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith('wt_session="";')
    assert "Max-Age=0" in cookie


def test_token_is_random_and_32_bytes(db_engine: Engine, clock: FakeClock) -> None:
    first = sessions.create_session(db_engine)
    second = sessions.create_session(db_engine)

    assert first != second
    assert len(first) >= 43


def test_no_plain_token_in_the_db(db_engine: Engine, clock: FakeClock) -> None:
    token = sessions.create_session(db_engine)

    with db_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM session")).all()
    assert len(rows) == 1
    assert all(token not in str(value) for value in rows[0])
    assert rows[0].token_hash == sessions.hash_token(token)


def test_new_session_is_valid(db_engine: Engine, clock: FakeClock) -> None:
    token = sessions.create_session(db_engine)

    assert sessions.touch_session(db_engine, token) is True


def test_unknown_token_is_not_valid(db_engine: Engine, clock: FakeClock) -> None:
    assert sessions.touch_session(db_engine, "no-such-token") is False


def test_session_expires_after_30_days_with_no_use(
    db_engine: Engine, clock: FakeClock
) -> None:
    token = sessions.create_session(db_engine)

    clock.advance(timedelta(days=30).total_seconds())

    assert sessions.touch_session(db_engine, token) is False


def test_each_use_moves_the_expiry(db_engine: Engine, clock: FakeClock) -> None:
    token = sessions.create_session(db_engine)

    for _ in range(3):
        clock.advance(timedelta(days=29).total_seconds())
        assert sessions.touch_session(db_engine, token) is True

    with Session(db_engine) as session:
        row = session.exec(select(AuthSession)).one()
    assert row.last_seen == clock.now()
    assert row.expires == clock.now() + timedelta(days=30)


def test_delete_session(db_engine: Engine, clock: FakeClock) -> None:
    token = sessions.create_session(db_engine)
    other = sessions.create_session(db_engine)

    sessions.delete_session(db_engine, token)

    assert sessions.touch_session(db_engine, token) is False
    assert sessions.touch_session(db_engine, other) is True


def test_delete_all_sessions(db_engine: Engine, clock: FakeClock) -> None:
    tokens = [sessions.create_session(db_engine) for _ in range(3)]

    sessions.delete_all_sessions(db_engine)

    assert all(sessions.touch_session(db_engine, token) is False for token in tokens)


def test_delete_unknown_session_does_nothing(
    db_engine: Engine, clock: FakeClock
) -> None:
    token = sessions.create_session(db_engine)

    sessions.delete_session(db_engine, "not-a-token")

    assert sessions.touch_session(db_engine, token) is True
