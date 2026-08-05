"""Summary Analytics API for synthetic prescription sessions."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.security.rbac import require_pharmacist
from app.services import prescription_service
from app.services.analytics.compute import compute_session_analytics
from app.services.analytics.pii import FORBIDDEN_KEYS, assert_no_pii_keys

router = APIRouter(prefix="/prescriptions", tags=["summary-analytics"])


def _invalidate_analytics_cache(session) -> None:
    if hasattr(session, "analytics_fingerprint"):
        session.analytics_fingerprint = None
        session.analytics_json = None


@router.get("/{anonymous_evaluation_id}/analytics")
def get_analytics(
    anonymous_evaluation_id: str,
    refresh: bool = Query(default=False),
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    session = prescription_service.get_owned_session(db, pharmacist, anonymous_evaluation_id)
    result = compute_session_analytics(db, session, force=refresh)
    try:
        assert_no_pii_keys(result)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Extra guard: no forbidden keys as string values either in top-level
    blob = json.dumps(result).lower()
    for key in FORBIDDEN_KEYS:
        if f'"{key}"' in blob:
            raise HTTPException(status_code=500, detail="PII key leaked into analytics response")
    return result


@router.get("/{anonymous_evaluation_id}/analytics/export")
def export_analytics(
    anonymous_evaluation_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    table: str = Query(
        default="all",
        pattern="^(all|medicine_performance|field_comparison|entity_metrics|therapeutic_alternative_metrics)$",
    ),
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    session = prescription_service.get_owned_session(db, pharmacist, anonymous_evaluation_id)
    result = compute_session_analytics(db, session, force=False)
    if not result.get("available"):
        raise HTTPException(status_code=422, detail=result.get("message") or "Analytics not available")

    assert_no_pii_keys(result)

    if format == "json":
        payload = result if table == "all" else _table_slice(result, table)
        return Response(
            content=json.dumps(payload, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="analytics_{anonymous_evaluation_id[:8]}_{table}.json"'
            },
        )

    rows = _csv_rows(result, table)
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        buf.write("")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{table}_{anonymous_evaluation_id[:8]}.csv"'
        },
    )


def _table_slice(result: dict, table: str) -> dict:
    mapping = {
        "medicine_performance": result.get("medicine_performance") or [],
        "field_comparison": result.get("comparison_rows") or [],
        "entity_metrics": result.get("entity_metrics") or [],
        "therapeutic_alternative_metrics": (result.get("alternative_metrics") or {}).get("per_medicine")
        or [],
    }
    return {"table": table, "demo_label": result.get("demo_label"), "rows": mapping[table]}


def _csv_rows(result: dict, table: str) -> list[dict]:
    if table == "all":
        # Prefer field comparison as default multi-table export primary
        return result.get("comparison_rows") or []
    return _table_slice(result, table)["rows"]
