"""Tests for wt.auth.totp."""

from urllib.parse import parse_qs, urlparse

import pyotp
import pytest

from wt.auth import totp
from wt.clock import FakeClock


def code_at(secret: str, clock: FakeClock, steps: int) -> str:
    return pyotp.TOTP(secret).at(clock.now() + steps * totp.STEP)


def current_step(clock: FakeClock) -> int:
    return int(clock.now().timestamp()) // 30


def test_new_secret_is_base32_and_random() -> None:
    first, second = totp.new_secret(), totp.new_secret()

    assert first != second
    assert len(first) >= 32
    pyotp.TOTP(first).now()


def test_provisioning_uri_has_the_issuer() -> None:
    uri = totp.provisioning_uri("JBSWY3DPEHPK3PXP")

    parsed = urlparse(uri)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "otpauth"
    assert parsed.netloc == "totp"
    assert query["issuer"] == ["Watch Tower"]
    assert query["secret"] == ["JBSWY3DPEHPK3PXP"]


@pytest.mark.parametrize("steps", [-1, 0, 1])
def test_codes_in_the_window_pass_and_give_the_step(
    clock: FakeClock, steps: int
) -> None:
    secret = totp.new_secret()

    step = totp.verify(secret, code_at(secret, clock, steps), last_step=None)

    assert step == current_step(clock) + steps


@pytest.mark.parametrize("steps", [-2, 2])
def test_codes_outside_the_window_fail(clock: FakeClock, steps: int) -> None:
    secret = totp.new_secret()

    assert totp.verify(secret, code_at(secret, clock, steps), last_step=None) is None


def test_the_same_code_twice_fails(clock: FakeClock) -> None:
    secret = totp.new_secret()
    code = code_at(secret, clock, 0)

    step = totp.verify(secret, code, last_step=None)

    assert step is not None
    assert totp.verify(secret, code, last_step=step) is None


def test_an_older_step_than_the_last_fails(clock: FakeClock) -> None:
    secret = totp.new_secret()

    late = totp.verify(secret, code_at(secret, clock, 1), last_step=None)

    assert totp.verify(secret, code_at(secret, clock, 0), last_step=late) is None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "١٢٣٤٥٦"])
def test_bad_code_format_fails(clock: FakeClock, code: str) -> None:
    assert totp.verify(totp.new_secret(), code, last_step=None) is None


def test_spaces_in_the_code_are_ignored(clock: FakeClock) -> None:
    secret = totp.new_secret()
    code = code_at(secret, clock, 0)

    assert totp.verify(
        secret, f" {code[:3]} {code[3:]} ", last_step=None
    ) == current_step(clock)
