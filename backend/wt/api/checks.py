"""Version check API: "Check now" and the check status."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from wt.api.deps import Ctx
from wt.context import AppContext
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
async def start_check(ctx: Ctx) -> CheckStatusOut:
    """Start a check run in the background. 409 if a run is active."""
    if ctx.checker.running:
        raise HTTPException(409, "A check is running")
    task = asyncio.create_task(ctx.checker.run())
    _runs.add(task)
    task.add_done_callback(_runs.discard)
    return await asyncio.to_thread(_status_out, ctx, True)


@router.get("/status")
def check_status(ctx: Ctx) -> CheckStatusOut:
    return _status_out(ctx, ctx.checker.running)


def _status_out(ctx: AppContext, running: bool) -> CheckStatusOut:
    status = load_check_status(ctx.engine)
    return CheckStatusOut(
        running=running, last_run=status.last_run, counts=status.counts
    )
