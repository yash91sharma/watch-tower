"""Tests for the session cookie helpers in wt.api.deps."""

from fastapi import Response

from wt.api.deps import clear_cookie, set_cookie


def test_cookie_flags() -> None:
    response = Response()

    set_cookie(response, "tok")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("wt_session=tok;")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=2592000" in cookie


def test_clear_cookie() -> None:
    response = Response()

    clear_cookie(response)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith('wt_session="";')
    assert "Max-Age=0" in cookie
