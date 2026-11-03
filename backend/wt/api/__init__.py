"""HTTP API: routes and SSE. All routes are under /api."""

from fastapi import APIRouter

# The routes of all API modules go on this router.
router = APIRouter(prefix="/api")
