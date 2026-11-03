"""Route dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, Response

from wt.auth import sessions
from wt.context import AppContext


def get_ctx(request: Request) -> AppContext:
    """The app context from the lifespan."""
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]
SessionCookie = Annotated[str | None, Cookie(alias=sessions.COOKIE)]


def require_session(
    ctx: Ctx, response: Response, wt_session: SessionCookie = None
) -> None:
    """401 with no valid session. Else renew the session and the cookie."""
    if wt_session is None or not sessions.touch_session(ctx.engine, wt_session):
        raise HTTPException(401, "Log in first")
    sessions.set_cookie(response, wt_session)
