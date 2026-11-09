"""HTTP API: routes and SSE. All routes are under /api.

Only /api/health and /api/auth/* are public. All other routes go on the `protected`
router, which needs a session.
"""

from fastapi import APIRouter, Depends

from wt.api import auth, checks, config_file, containers, health, logs, settings, stream
from wt.api.deps import require_session
from wt.api.errors import ErrorBody

# The OpenAPI schema shows the WT error shape for all errors.
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    422: {"model": ErrorBody, "description": "Validation error"},
    "default": {"model": ErrorBody, "description": "Error"},
}

router = APIRouter(prefix="/api", responses=ERROR_RESPONSES)
router.include_router(health.router)
router.include_router(auth.router)

protected = APIRouter(dependencies=[Depends(require_session)])
protected.include_router(settings.router)
protected.include_router(config_file.router)
protected.include_router(checks.router)
protected.include_router(containers.router)
protected.include_router(logs.router)
protected.include_router(stream.router)

router.include_router(protected)
