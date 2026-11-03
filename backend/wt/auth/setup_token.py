"""One-time setup token.

At start, if no admin is set up, WT makes a random token and writes it to its log once.
The setup page asks for it. The token is in memory only and works for one setup.
"""

import hmac
import logging
import secrets
from typing import Self

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db.models import Admin

log = logging.getLogger(__name__)

TOKEN_BYTES = 32


class SetupToken:
    def __init__(self, value: str | None) -> None:
        self.value = value
        # The TOTP secret from setup begin. Setup finish checks the code against it.
        self.pending_secret: str | None = None

    @classmethod
    def at_start(cls, engine: Engine) -> Self:
        """Make a token if there is no admin, and log it."""
        with Session(engine) as session:
            has_admin = session.exec(select(Admin)).first() is not None
        if has_admin:
            return cls(None)
        value = secrets.token_urlsafe(TOKEN_BYTES)
        log.warning("No admin is set up. Open WT and use this setup token: %s", value)
        return cls(value)

    def check(self, token: str) -> bool:
        """True if `token` is the setup token. Constant-time compare."""
        if self.value is None:
            return False
        return hmac.compare_digest(self.value.encode(), token.encode())

    def use(self) -> None:
        """The setup is done. The token does not work again."""
        self.value = None
        self.pending_secret = None
