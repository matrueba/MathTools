"""Serves the built frontend, with SPA-aware fallback for client-side routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from constants.web import FRONTEND_DIST_DIR


class SPAStaticFiles(StaticFiles):
    """
    StaticFiles that falls back to index.html for unknown paths.

    The frontend uses BrowserRouter, so deep links like /projects/mathtools
    have no file on disk — without this, reloading any non-root page 404s.
    """

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            # Only fall back for navigation paths. A missing asset must stay a
            # 404 — answering a .js request with index.html gives the browser
            # HTML where it expects a script, and the page fails silently
            # with no error to debug.
            if "." in path.rsplit("/", 1)[-1]:
                raise
            # Same for the API: an unknown or removed endpoint must 404, not
            # answer an API client with HTML and a 200.
            if path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def mount_frontend(app: FastAPI, repo_root: Path) -> None:
    """
    Serve the built frontend when it exists.

    In development you run the Vite dev server instead, which proxies /api
    back here.
    """
    dist_dir = repo_root / FRONTEND_DIST_DIR
    if dist_dir.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="frontend")
