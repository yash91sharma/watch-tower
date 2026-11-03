"""Admin reset from the host: `docker exec wt wt reset-admin`, then `docker restart wt`.

The reset deletes the admin (password and TOTP secret) and all sessions. The restart clears
the state in memory (login limit) and makes a new setup token.
"""

from sqlalchemy import Engine
from sqlmodel import Session, delete

from wt.db.models import Admin, AuthSession

NEXT_STEP = "Restart WT (docker restart wt). Then get the setup token from the WT log."


def reset_admin(engine: Engine) -> None:
    with Session(engine) as session:
        session.exec(delete(Admin))
        session.exec(delete(AuthSession))
        session.commit()
