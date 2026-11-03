"""GET /api/health: the container healthcheck. No auth."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from wt.api.deps import Ctx

log = logging.getLogger(__name__)
router = APIRouter()


class Health(BaseModel):
    status: str


@router.get("/health")
def health(ctx: Ctx) -> Health:
    """200 if the DB answers, else 503."""
    try:
        with ctx.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        log.exception("Health check: the DB does not answer")
        raise HTTPException(503, "The database does not answer") from None
    return Health(status="ok")
