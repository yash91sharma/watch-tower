"""Login sessions.

The cookie has a random token. The DB has only its SHA-256 hash, so a copy of the DB
cannot log in. A session expires after 30 days with no use. Each use moves the expiry.
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import Engine
from sqlmodel import Session

from wt import clock
from wt.db.models import AuthSession

COOKIE = "wt_session"
TOKEN_BYTES = 32
MAX_IDLE = timedelta(days=30)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(engine: Engine) -> str:
    """Make a session. Give the token for the cookie."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = clock.now()
    with Session(engine) as session:
        session.add(
            AuthSession(
                token_hash=hash_token(token),
                created=now,
                expires=now + MAX_IDLE,
                last_seen=now,
            )
        )
        session.commit()
    return token


def touch_session(engine: Engine, token: str) -> bool:
    """True if the session is valid. Then move its expiry to 30 days from now."""
    now = clock.now()
    with Session(engine) as session:
        row = session.get(AuthSession, hash_token(token))
        if row is None or row.expires <= now:
            return False
        row.last_seen = now
        row.expires = now + MAX_IDLE
        session.commit()
    return True


def delete_session(engine: Engine, token: str) -> None:
    with Session(engine) as session:
        row = session.get(AuthSession, hash_token(token))
        if row is not None:
            session.delete(row)
            session.commit()
