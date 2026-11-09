"""Version check API: "Check now" and the check status."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from wt.api.deps import Ctx
from wt.context import AppContext
from wt.docker.parse import group_label
from wt.versions.check import load_check_status

router = APIRouter(prefix="/checks", tags=["checks"])


class CheckStatusOut(BaseModel):
    running: bool
    last_run: datetime | None
    # Status value -> number of containers.
    counts: dict[str, int]


@router.post("", status_code=202)
async def start_check(ctx: Ctx, group: str | None = None) -> CheckStatusOut:
    """Start a check run in the background. 409 if a run is active.

    With `group` (a group label of the container list), check only the containers of
    that app. 404 if no live container is in the group.
    """
    names = None
    if group is not None:
        names = await asyncio.to_thread(_group_names, ctx, group)
        if not names:
            raise HTTPException(404, f"No group {group!r}")
    if ctx.checker.running:
        raise HTTPException(409, "A check is running")
    ctx.checker.start(names)
    return await asyncio.to_thread(_status_out, ctx, True)


@router.get("/status")
def check_status(ctx: Ctx) -> CheckStatusOut:
    return _status_out(ctx, ctx.checker.running)


def _group_names(ctx: AppContext, label: str) -> list[str]:
    """The live, not excluded containers with this group label (as in the list)."""
    with Session(ctx.engine) as session:
        return [
            row.name
            for row, _ in ctx.inventory.live_rows(session)
            if group_label(row.compose_project) == label
        ]


def _status_out(ctx: AppContext, running: bool) -> CheckStatusOut:
    status = load_check_status(ctx.engine)
    return CheckStatusOut(
        running=running, last_run=status.last_run, counts=status.counts
    )
