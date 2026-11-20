"""The built frontend: static files and the SPA fallback.

There is no catch-all route. When no route matches (404), a GET or HEAD outside /api gets
the file from the static dir, or index.html (the React app reads the path). All other
404s get the JSON error.
"""

import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from starlette.exceptions import HTTPException

from wt.api.errors import error_response

log = logging.getLogger(__name__)

# The Dockerfile copies the frontend build here.
STATIC_DIR = Path(__file__).parents[1] / "static"

# Vite puts files with a content hash in their names in assets/.
IMMUTABLE = "public, max-age=31536000, immutable"


def install(app: FastAPI, static_dir: Path) -> None:
    """Serve the frontend from `static_dir`. If it does not exist, only the API works."""
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        log.warning("No frontend at %s. Only the API works.", root)

    async def not_found(request: Request, exc: Exception) -> Response:
        path = request.url.path
        is_api = path == "/api" or path.startswith("/api/")
        if request.method in ("GET", "HEAD") and not is_api and index.is_file():
            gzip_ok = _accepts_gzip(request.headers.get("accept-encoding", ""))
            return _file_response(root, path.lstrip("/"), index, gzip_ok)
        if isinstance(exc, HTTPException):
            return error_response(404, str(exc.detail), exc.headers)
        return error_response(404, "Not Found")

    app.add_exception_handler(404, not_found)


def _file_response(
    root: Path, relative: str, index: Path, gzip_ok: bool
) -> FileResponse:
    """The file at `relative` if it is in `root`, else index.html.

    If the build made a gzip copy (`<file>.gz`) and the client accepts gzip, send the copy.
    """
    file = (root / relative).resolve()
    if not (file.is_relative_to(root) and file.is_file()):
        file = index
    immutable = file.is_relative_to(root / "assets")
    headers = {"Cache-Control": IMMUTABLE if immutable else "no-cache"}
    compressed = file.with_name(f"{file.name}.gz")
    if not compressed.is_file():
        return FileResponse(file, headers=headers)
    headers["Vary"] = "Accept-Encoding"
    if not gzip_ok:
        return FileResponse(file, headers=headers)
    headers["Content-Encoding"] = "gzip"
    media_type, _ = mimetypes.guess_type(file.name)
    return FileResponse(compressed, media_type=media_type, headers=headers)


def _accepts_gzip(accept_encoding: str) -> bool:
    """True if the Accept-Encoding header has gzip, with no "q=0"."""
    for item in accept_encoding.split(","):
        name, _, params = item.partition(";")
        if name.strip().lower() == "gzip" and params.replace(" ", "") != "q=0":
            return True
    return False
