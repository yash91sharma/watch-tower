"""HTTP API: routes and SSE. All routes are under /api.

Only /api/health and /api/auth/* are public. All other routes go on the `protected`
router, which needs a session.
"""

from fastapi import APIRouter, Depends

from wt.api import auth, config_file, health, settings
from wt.api.deps import require_session

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(auth.router)

protected = APIRouter(dependencies=[Depends(require_session)])
protected.include_router(settings.router)
protected.include_router(config_file.router)

router.include_router(protected)
