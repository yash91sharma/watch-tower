"""Route dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from wt.context import AppContext


def get_ctx(request: Request) -> AppContext:
    """The app context from the lifespan."""
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]
