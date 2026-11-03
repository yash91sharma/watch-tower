"""Tests for wt.auth.password."""

import pytest

from wt.auth.password import (
    MIN_LENGTH,
    PasswordTooShortError,
    hash_password,
    verify_password,
)

GOOD = "correct horse battery"


def test_hash_uses_argon2id_with_the_owasp_params() -> None:
    hashed = hash_password(GOOD)

    assert hashed.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert GOOD not in hashed


def test_same_password_gives_a_new_salt() -> None:
    assert hash_password(GOOD) != hash_password(GOOD)


def test_good_password_verifies() -> None:
    assert verify_password(hash_password(GOOD), GOOD) is True


def test_bad_password_fails() -> None:
    assert verify_password(hash_password(GOOD), GOOD + "x") is False


def test_bad_hash_fails() -> None:
    assert verify_password("not a hash", GOOD) is False


def test_short_password_is_rejected() -> None:
    with pytest.raises(PasswordTooShortError):
        hash_password("x" * (MIN_LENGTH - 1))


def test_password_of_min_length_is_accepted() -> None:
    assert verify_password(hash_password("x" * MIN_LENGTH), "x" * MIN_LENGTH)
