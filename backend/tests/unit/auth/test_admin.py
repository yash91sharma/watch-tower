"""Tests for wt.auth.admin: the one admin row (DB)."""

from sqlalchemy import Engine

from wt.auth.admin import create_admin, load_admin, use_totp_step


def test_no_admin_on_a_new_db(db_engine: Engine) -> None:
    assert load_admin(db_engine) is None


def test_create_admin_saves_the_row(db_engine: Engine) -> None:
    assert create_admin(db_engine, "hash", "SECRET", step=10)

    admin = load_admin(db_engine)
    assert admin is not None
    assert (admin.password_hash, admin.totp_secret, admin.last_totp_step) == (
        "hash",
        "SECRET",
        10,
    )


def test_a_second_admin_is_not_created(db_engine: Engine) -> None:
    create_admin(db_engine, "hash", "SECRET", step=10)

    assert not create_admin(db_engine, "other", "OTHER", step=11)
    admin = load_admin(db_engine)
    assert admin is not None
    assert admin.password_hash == "hash"


def test_use_totp_step_saves_a_newer_step(db_engine: Engine) -> None:
    create_admin(db_engine, "hash", "SECRET", step=10)

    assert use_totp_step(db_engine, 11)
    admin = load_admin(db_engine)
    assert admin is not None
    assert admin.last_totp_step == 11


def test_use_totp_step_rejects_the_same_or_an_older_step(db_engine: Engine) -> None:
    create_admin(db_engine, "hash", "SECRET", step=10)

    assert not use_totp_step(db_engine, 10)
    assert not use_totp_step(db_engine, 9)
    admin = load_admin(db_engine)
    assert admin is not None
    assert admin.last_totp_step == 10
