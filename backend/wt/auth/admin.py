"""The one admin row: create it at setup, read it at login, save the used TOTP step."""

from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, update

from wt.db.models import ADMIN_ID, Admin


def load_admin(engine: Engine) -> Admin | None:
    with Session(engine) as session:
        return session.get(Admin, ADMIN_ID)


def create_admin(
    engine: Engine, password_hash: str, totp_secret: str, step: int
) -> bool:
    """Save the admin. False if the admin exists (for example, a parallel setup)."""
    admin = Admin(
        id=ADMIN_ID,
        password_hash=password_hash,
        totp_secret=totp_secret,
        last_totp_step=step,
    )
    try:
        with Session(engine) as session:
            session.add(admin)
            session.commit()
    except IntegrityError:
        return False
    return True


def use_totp_step(engine: Engine, step: int) -> bool:
    """Save the TOTP step. False if a parallel login used this step or a newer one."""
    statement = (
        update(Admin)
        .where(col(Admin.id) == ADMIN_ID, col(Admin.last_totp_step) < step)
        .values(last_totp_step=step)
    )
    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()
    return result.rowcount == 1
