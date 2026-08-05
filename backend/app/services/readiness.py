"""Readiness / health payload builders."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.db.session import check_database
from app.services.production_guard import validate_runtime_settings


def build_health_payload(*, deep: bool = True) -> dict[str, Any]:
    database = check_database()
    catalog: dict[str, Any] = {"available": False}
    if deep:
        try:
            from app.services.datasets.overview import catalog_overview

            overview = catalog_overview()
            catalog = {
                "available": bool(overview.get("available")),
                "medicines": (overview.get("unified") or {}).get("medicines"),
                "aliases": (overview.get("unified") or {}).get("aliases"),
                "built_at": overview.get("built_at"),
                "sources": [s.get("id") for s in (overview.get("sources") or [])],
            }
            try:
                from app.services.datasets.warmup_status import get_warmup_status

                catalog["warmup"] = get_warmup_status()
            except Exception:  # noqa: BLE001
                catalog["warmup"] = {"status": "unknown"}
        except Exception as exc:  # noqa: BLE001
            catalog = {"available": False, "error": type(exc).__name__}

    warnings = validate_runtime_settings()
    components = {
        "database": database.get("status") == "ok",
        "catalog": bool(catalog.get("available")),
    }
    if database.get("status") != "ok":
        overall = "error"
    elif not catalog.get("available"):
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "status": overall,
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "phase": "award-path",
        "version": "0.2.0-award-path",
        "database": database,
        "catalog": catalog,
        "components": components,
        "settings_warnings": warnings if (settings.APP_ENV or "").lower() != "production" else [],
        "message": "API is running" if overall != "error" else "API unhealthy",
        "intended_use": (
            "Pharmacist decision-support only. Not clinical care; HITL confirmation is mandatory."
        ),
        "retention": {
            "retention_hours": settings.TEMP_FILE_RETENTION_HOURS,
            "delete_when_session_confirmed": settings.DELETE_TEMP_WHEN_SESSION_CONFIRMED,
        },
    }
