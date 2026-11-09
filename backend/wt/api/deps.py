"""Route dependencies and helpers: the app context, the container lookup and the session
cookie.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, Response
from sqlmodel import Session

from wt.auth import sessions
from wt.context import AppContext
from wt.db import find_container
from wt.db.models import Container
from wt.docker.inventory import Inventory, LiveContainer


def get_ctx(request: Request) -> AppContext:
    """The app context from the lifespan."""
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]
SessionCookie = Annotated[str | None, Cookie(alias=sessions.COOKIE)]


def get_container(session: Session, name: str) -> Container:
    """The container row by name. 404 if WT does not know it or it is excluded."""
    row = find_container(session, name)
    if row is None or not row.enabled:
        raise HTTPException(404, f"No container {name!r}")
    return row


def get_live(
    session: Session, inventory: Inventory, name: str
) -> tuple[Container, LiveContainer]:
    """The row and the live state of a container that is not excluded. 404 if it is not
    in Docker now.
    """
    row = get_container(session, name)
    live = inventory.get(name)
    if live is None:
        raise HTTPException(404, f"No container {name!r}")
    return row, live


def require_session(
    ctx: Ctx, response: Response, wt_session: SessionCookie = None
) -> None:
    """401 with no valid session. Else renew the session and the cookie."""
    if wt_session is None or not sessions.touch_session(ctx.engine, wt_session):
        raise HTTPException(401, "Log in first")
    set_cookie(response, wt_session)


def set_cookie(response: Response, token: str) -> None:
    """Set the session cookie. Set it again on each use, so that it lives as long as the session."""
    response.set_cookie(
        sessions.COOKIE,
        token,
        max_age=int(sessions.MAX_IDLE.total_seconds()),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def clear_cookie(response: Response) -> None:
    """Delete the session cookie."""
    response.delete_cookie(
        sessions.COOKIE, httponly=True, secure=True, samesite="strict", path="/"
    )
