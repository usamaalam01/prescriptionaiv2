"""Serve the built React SPA from FastAPI (HF Spaces / single-container deploy).

Only active when a built ``frontend/dist`` directory is present, so local
development (Vite dev server on :5173 proxying to the API) is unaffected. When
present, static assets are mounted and every non-API path falls through to
``index.html`` so client-side routing works on refresh/deep-link.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("pharmaassist.spa")

# Reserved server-side prefixes the SPA catch-all must never swallow.
_API_PREFIXES = ("/api", "/health", "/ready", "/docs", "/redoc", "/openapi.json")


def _resolve_dist() -> Path | None:
    """Locate the built frontend. Env override wins; else conventional locations."""
    import os

    env = os.environ.get("FRONTEND_DIST_DIR", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    # backend/app/web_spa.py -> repo layouts: <root>/frontend/dist, /app/frontend/dist
    candidates += [
        here.parents[2] / "frontend" / "dist",   # new/frontend/dist (dev tree)
        here.parents[2] / "static",               # backend/static (copied build)
        Path("/app/frontend/dist"),               # container layout
        Path("/app/static"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "index.html").is_file():
            return c
    return None


def mount_spa(app: FastAPI) -> bool:
    """Mount the SPA if a build exists. Returns True when mounted."""
    dist = _resolve_dist()
    if dist is None:
        logger.info("SPA not mounted — no built frontend/dist found (dev mode).")
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index_html = dist / "index.html"

    @app.get("/{full_path:path}")
    def spa_catch_all(full_path: str, request: Request):
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _API_PREFIXES):
            # Should have been handled by a real route; return JSON 404, not the SPA.
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Serve real static files (favicon, manifest, etc.) if they exist,
        # otherwise fall back to index.html for client-side routing.
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist)  # guard against path traversal
        except ValueError:
            return FileResponse(index_html)
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_html)

    logger.info("SPA mounted from %s", dist)
    return True
