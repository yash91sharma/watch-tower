"""HTTP API: routes and SSE. All routes are under /api."""

from fastapi import APIRouter

from wt.api import auth, health

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(auth.router)
