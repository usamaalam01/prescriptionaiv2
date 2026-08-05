from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.admin import RegistrationRequest
from app.models.auth import User
from app.schemas.registration import DecisionIn, RegistrationListItem
from app.security.rbac import require_administrator
from app.services import admin_dashboard
from app.services.admin_service import decide_registration
from app.services.datasets.overview import catalog_overview

router = APIRouter(prefix="/admin", tags=["administrator"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    return admin_dashboard.dashboard_summary(db)


@router.get("/catalog")
def catalog(
    _: User = Depends(require_administrator),
):
    return catalog_overview()


@router.get("/prescriptions")
def prescriptions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    items = admin_dashboard.list_prescription_sessions(db, limit=limit)
    return {
        "items": items,
        "disclaimer": (
            "Live sessions only: self-registered pharmacists, non-mock OCR. "
            "No patient identifiers or fabricated rows."
        ),
    }


@router.get("/analytics/prescriptions")
def analytics_prescriptions(
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    """CER / WER / entity F1 / BertScore at full-prescription level."""
    return admin_dashboard.prescription_analytics(db, limit=limit)


@router.get("/registrations", response_model=list[RegistrationListItem])
def list_registrations(
    status: str | None = "pending_review",
    include_test: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    from app.services.admin_dashboard import _is_demo_or_test_username

    query = select(RegistrationRequest, User).join(User, User.id == RegistrationRequest.user_id)
    if status:
        query = query.where(RegistrationRequest.status == status)
    rows = db.execute(query).all()
    items = []
    for req, user in rows:
        if not include_test and _is_demo_or_test_username(user.username):
            continue
        items.append(
            RegistrationListItem(
                id=req.id,
                user_id=req.user_id,
                username=user.username,
                requested_role=req.requested_role,
                status=req.status,
                submitted_at=req.submitted_at.isoformat() if req.submitted_at else None,
                encrypted_registration_data=bool(user.encrypted_pharmacist_registration_id),
            )
        )
    return items


@router.post("/registrations/{request_id}/approve")
def approve(
    request_id: str,
    body: DecisionIn,
    admin: User = Depends(require_administrator),
    db: Session = Depends(get_db),
):
    item = decide_registration(
        db,
        admin,
        request_id,
        approve=True,
        confirmed_role=body.confirmed_role,
        reason=body.reason,
    )
    return {"id": item.id, "status": item.status}


@router.post("/registrations/{request_id}/reject")
def reject(
    request_id: str,
    body: DecisionIn,
    admin: User = Depends(require_administrator),
    db: Session = Depends(get_db),
):
    item = decide_registration(
        db,
        admin,
        request_id,
        approve=False,
        confirmed_role=body.confirmed_role,
        reason=body.reason,
    )
    return {"id": item.id, "status": item.status}


@router.get("/retention")
def retention_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    from app.services.retention import retention_status

    return retention_status(db)


@router.post("/retention/purge")
def retention_purge(
    db: Session = Depends(get_db),
    _: User = Depends(require_administrator),
):
    from app.services.retention import purge_expired_temporary_files

    return purge_expired_temporary_files(db)
