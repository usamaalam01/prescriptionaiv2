"""PharmaAssist API — decision-support HITL platform (FDA NDC / DrugBank / SPL)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.services.production_guard import validate_runtime_settings
from app.services.readiness import build_health_payload


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    # HF Spaces only (guarded by SPACE_ID): redirect caches, download runtime
    # artefacts, apply migrations. No-op locally.
    from app.startup_hf import run as hf_provision

    hf_provision()
    validate_runtime_settings()
    if settings.PURGE_EXPIRED_ON_STARTUP:
        try:
            from app.db.session import SessionLocal
            from app.services.retention import purge_expired_temporary_files

            db = SessionLocal()
            try:
                result = purge_expired_temporary_files(db)
                import logging

                logging.getLogger("pharmaassist.retention").info(
                    "startup_purge purged_count=%s", result.get("purged_count")
                )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("pharmaassist.retention").warning(
                "startup_purge_skipped error=%s", type(exc).__name__
            )

    # Stage catalog + alias indexes off the request path (Docker bind mounts are slow).
    import threading

    threading.Thread(
        target=_warmup_medicine_catalog,
        name="catalog-warmup",
        daemon=True,
    ).start()
    yield


def _warmup_medicine_catalog() -> None:
    import logging
    import time

    from app.services.datasets.warmup_status import set_warmup_status

    log = logging.getLogger("pharmaassist.catalog")
    started = time.perf_counter()
    set_warmup_status("pending")
    try:
        from app.services.datasets.catalog_store import (
            _alias_rows,
            _runtime_catalog_copy,
            catalog_available,
        )
        from app.services.datasets.match import _alias_indexes, suggest_medicines

        if not catalog_available():
            set_warmup_status("skipped", error="catalog_unavailable")
            log.warning("catalog_warmup skipped — catalog unavailable")
            return
        _runtime_catalog_copy()
        n = len(_alias_rows())
        _alias_indexes()
        suggest_medicines("Amoxicillin", top_k=1)
        elapsed = time.perf_counter() - started
        set_warmup_status("ready", aliases=n, seconds=elapsed)
        log.info(
            "catalog_warmup complete aliases=%s seconds=%.1f",
            n,
            elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        set_warmup_status("failed", error=f"{type(exc).__name__}: {str(exc)[:120]}")
        log.warning(
            "catalog_warmup failed error=%s detail=%s",
            type(exc).__name__,
            str(exc)[:160],
        )


_cors = [o.strip() for o in (settings.CORS_ORIGINS or "").split(",") if o.strip()]
if not _cors:
    _cors = ["http://localhost:5173", "http://127.0.0.1:5173"]

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-Powered Pharma Assist — University of Liverpool CSCK700. "
        "Pharmacist decision-support with FDA NDC / DrugBank / FDA SPL catalog HITL. "
        "Not for clinical care; pharmacist confirmation is mandatory."
    ),
    version="0.2.0-award-path",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    """Liveness + shallow readiness (safe for load balancers)."""
    return build_health_payload(deep=True)


@app.get("/ready")
def ready():
    """Explicit readiness probe (same payload; reserved for k8s-style checks)."""
    payload = build_health_payload(deep=True)
    # 200 even when degraded (catalog missing) so compose stays up in demos;
    # return 503 only when database is down.
    if payload["status"] == "error":
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=payload)
    return payload


# Serve the built React SPA when present (single-container / HF Spaces deploy).
# No-op in local dev (Vite serves the frontend on :5173). Mounted LAST so the
# catch-all never shadows /api/v1, /health, /ready, or /docs.
from app.web_spa import mount_spa  # noqa: E402

mount_spa(app)
