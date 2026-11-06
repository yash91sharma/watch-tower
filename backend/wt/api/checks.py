"""Version check API: "Check now" and the check status."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from wt.api.containers import OTHER_LABEL
from wt.api.deps import Ctx
from wt.context import AppContext
from wt.db import find_container
from wt.versions.check import load_check_status

router = APIRouter(prefix="/checks", tags=["checks"])

# Keep a reference to each background run, so that it is not garbage collected.
_runs: set[asyncio.Task[bool]] = set()


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
    task = asyncio.create_task(ctx.checker.run(names))
    _runs.add(task)
    task.add_done_callback(_runs.discard)
    return await asyncio.to_thread(_status_out, ctx, True)


@router.get("/status")
def check_status(ctx: Ctx) -> CheckStatusOut:
    return _status_out(ctx, ctx.checker.running)


def _group_names(ctx: AppContext, label: str) -> list[str]:
    """The live, not excluded containers with this group label (as in the list)."""
    names: list[str] = []
    with Session(ctx.engine) as session:
        for name in ctx.inventory.names():
            row = find_container(session, name)
            if (
                row is not None
                and row.enabled
                and (row.compose_project or OTHER_LABEL) == label
            ):
                names.append(name)
    return names


def _status_out(ctx: AppContext, running: bool) -> CheckStatusOut:
    status = load_check_status(ctx.engine)
    return CheckStatusOut(
        running=running, last_run=status.last_run, counts=status.counts
    )
