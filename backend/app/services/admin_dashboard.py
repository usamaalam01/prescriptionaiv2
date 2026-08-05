"""Administrator portal aggregates — live DB only (no fabricated / demo KPIs)."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import RegistrationStatus, UserStatus
from app.db.seed import DEV_USERS
from app.models.admin import RegistrationRequest
from app.models.auth import User
from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession
from app.services.analytics.compute import compute_session_analytics
from app.services.datasets.overview import catalog_overview

_SEED_USERNAMES = {u[0] for u in DEV_USERS}
_TEST_PHARM_RE = re.compile(r"^pharm_[0-9a-f]{8,}$", re.IGNORECASE)


def _is_demo_or_test_username(username: str | None) -> bool:
    if not username:
        return True
    if username in _SEED_USERNAMES:
        return True
    return bool(_TEST_PHARM_RE.match(username))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _owner(db: Session, session: ReviewSession) -> User | None:
    return db.get(User, session.pharmacist_user_id)


def _has_self_registration(db: Session, user_id: str) -> bool:
    return (
        db.scalar(select(RegistrationRequest.id).where(RegistrationRequest.user_id == user_id).limit(1))
        is not None
    )


def _latest_ocr(db: Session, session_id: str) -> OcrJob | None:
    return db.scalar(
        select(OcrJob).where(OcrJob.session_id == session_id).order_by(OcrJob.created_at.desc()).limit(1)
    )


def _session_is_real(db: Session, session: ReviewSession) -> tuple[bool, str]:
    """
    Real operational session:
    - owned by a self-registered pharmacist (not seed / pytest pharm_<hex>)
    - if OCR ran, latest job must be non-mock (exclude synthetic OCR pipelines)
    """
    user = _owner(db, session)
    if user is None or _is_demo_or_test_username(user.username):
        return False, "seed_or_test_owner"
    if not _has_self_registration(db, user.id):
        return False, "not_self_registered"
    ocr = _latest_ocr(db, session.id)
    if ocr is not None and ocr.is_mock:
        return False, "mock_ocr"
    return True, "ok"


def dashboard_summary(db: Session) -> dict[str, Any]:
    reg_rows = db.execute(
        select(RegistrationRequest, User)
        .join(User, User.id == RegistrationRequest.user_id)
        .order_by(RegistrationRequest.submitted_at.desc())
    ).all()

    real_regs = [(req, user) for req, user in reg_rows if not _is_demo_or_test_username(user.username)]
    excluded_test_regs = len(reg_rows) - len(real_regs)

    pending_registrations = sum(
        1 for req, _ in real_regs if req.status == RegistrationStatus.PENDING_REVIEW.value
    )
    approved_registrations = sum(
        1 for req, _ in real_regs if req.status == RegistrationStatus.APPROVED.value
    )
    rejected_registrations = sum(
        1 for req, _ in real_regs if req.status == RegistrationStatus.REJECTED.value
    )

    pharmacist_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for req, user in real_regs:
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        pharmacist_entries.append(
            {
                "username": user.username,
                "status": user.status,
                "is_active": user.is_active,
                "registration_status": req.status,
                "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
            }
        )

    pharmacists_active = sum(
        1 for e in pharmacist_entries if e["status"] == UserStatus.ACTIVE.value and e["is_active"]
    )
    pharmacists_pending = sum(1 for e in pharmacist_entries if e["status"] == UserStatus.PENDING.value)

    all_sessions = db.scalars(select(ReviewSession)).all()
    real_sessions: list[ReviewSession] = []
    excluded_sessions = {"seed_or_test_owner": 0, "not_self_registered": 0, "mock_ocr": 0}
    for s in all_sessions:
        ok, reason = _session_is_real(db, s)
        if ok:
            real_sessions.append(s)
        else:
            excluded_sessions[reason] = excluded_sessions.get(reason, 0) + 1

    real_ids = [s.id for s in real_sessions]
    sessions_submitted = sum(1 for s in real_sessions if s.status == "submitted")
    sessions_in_progress = sum(
        1 for s in real_sessions if s.status in {"uploaded", "ocr_completed", "in_review", "ready"}
    )

    if real_ids:
        reviewed_sessions = (
            db.scalar(
                select(func.count(func.distinct(PrescriptionMedicine.session_id))).where(
                    PrescriptionMedicine.session_id.in_(real_ids),
                    PrescriptionMedicine.pharmacist_status == "confirmed",
                )
            )
            or 0
        )
        medicines_confirmed = (
            db.scalar(
                select(func.count())
                .select_from(PrescriptionMedicine)
                .where(
                    PrescriptionMedicine.session_id.in_(real_ids),
                    PrescriptionMedicine.pharmacist_status == "confirmed",
                )
            )
            or 0
        )
    else:
        reviewed_sessions = 0
        medicines_confirmed = 0

    catalog = catalog_overview()
    return {
        "disclaimer": (
            "All administrator KPIs are live database counts — nothing is fabricated or demo-seeded. "
            "Excluded: seed logins (admin/pharmacist/reviewer), pytest usernames (pharm_<hex>), "
            "accounts without self-registration, and sessions whose latest OCR job is mock/synthetic. "
            "Catalog figures are from the local FDA NDC + DrugBank + SPL index build (reference data, not demo KPIs)."
        ),
        "data_policy": {
            "exclude_seed_users": True,
            "exclude_test_usernames": True,
            "require_self_registration": True,
            "exclude_mock_ocr_sessions": True,
            "excluded_registration_accounts": excluded_test_regs,
            "excluded_sessions": excluded_sessions,
        },
        "pharmacists": {
            "total": len(pharmacist_entries),
            "active": pharmacists_active,
            "pending": pharmacists_pending,
            "list": pharmacist_entries,
        },
        "registrations": {
            "pending_review": pending_registrations,
            "approved": approved_registrations,
            "rejected": rejected_registrations,
            "excluded_test_accounts": excluded_test_regs,
        },
        "prescriptions": {
            "sessions_total": len(real_sessions),
            "reviewed_with_confirmations": reviewed_sessions,
            "submitted": sessions_submitted,
            "in_progress_estimate": sessions_in_progress,
            "medicines_confirmed": medicines_confirmed,
        },
        "catalog": {
            "available": catalog.get("available"),
            "built_at": catalog.get("built_at"),
            "medicines": (catalog.get("unified") or {}).get("medicines"),
            "products": (catalog.get("unified") or {}).get("products"),
            "aliases": (catalog.get("unified") or {}).get("aliases"),
            "label_sections": (catalog.get("unified") or {}).get("label_sections"),
            "sources": catalog.get("sources") or [],
        },
    }


def list_prescription_sessions(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ReviewSession).order_by(ReviewSession.created_at.desc()).limit(min(limit * 5, 500))
    ).all()
    out: list[dict[str, Any]] = []
    excluded = 0
    for s in rows:
        ok, _reason = _session_is_real(db, s)
        if not ok:
            excluded += 1
            continue
        pharmacist = _owner(db, s)
        ocr = _latest_ocr(db, s.id)
        confirmed = (
            db.scalar(
                select(func.count())
                .select_from(PrescriptionMedicine)
                .where(
                    PrescriptionMedicine.session_id == s.id,
                    PrescriptionMedicine.pharmacist_status == "confirmed",
                )
            )
            or 0
        )
        total_meds = (
            db.scalar(
                select(func.count())
                .select_from(PrescriptionMedicine)
                .where(PrescriptionMedicine.session_id == s.id)
            )
            or 0
        )
        out.append(
            {
                "session_id": s.id,
                "status": s.status,
                "pharmacist_username": pharmacist.username if pharmacist else None,
                "original_filename": s.original_filename,
                "medicines_total": total_meds,
                "medicines_confirmed": confirmed,
                "ocr_is_mock": bool(ocr.is_mock) if ocr else None,
                "has_analytics": bool(s.analytics_json),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _extract_prescription_metrics(
    payload: dict[str, Any],
    session: ReviewSession,
    *,
    pharmacist_username: str | None = None,
) -> dict[str, Any]:
    text = (payload.get("text_metrics") or {}).get("full_prescription") or {}
    # Exact = string audit (case/spacing count). Normalized = format/synonym equivalence.
    # Admin OCR-quality KPIs use normalized so Ibuprofen/ibuprofen and 400mg/400 mg do not tank F1.
    aggs_exact = payload.get("entity_aggregates") or {}
    aggs_norm = payload.get("entity_aggregates_normalized") or {}
    aggs = aggs_norm if aggs_norm.get("micro_average_f1") is not None else aggs_exact
    rx_bert = payload.get("prescription_bertscore")
    return {
        "session_id": session.id,
        "status": session.status,
        "pharmacist_username": pharmacist_username,
        "cer": text.get("final_cer"),
        "wer": text.get("final_wer"),
        "entity_precision": aggs.get("micro_average_precision"),
        "entity_recall": aggs.get("micro_average_recall"),
        "entity_f1": aggs.get("micro_average_f1"),
        "entity_f1_exact": aggs_exact.get("micro_average_f1"),
        "entity_f1_normalized": aggs_norm.get("micro_average_f1"),
        "entity_match_mode": aggs.get("match_mode") or "exact",
        "bertscore_precision": (rx_bert or {}).get("precision") if isinstance(rx_bert, dict) else None,
        "bertscore_recall": (rx_bert or {}).get("recall") if isinstance(rx_bert, dict) else None,
        "bertscore_f1": (rx_bert or {}).get("f1") if isinstance(rx_bert, dict) else None,
        "bertscore_status": payload.get("bertscore_status"),
        "medicines_confirmed": (payload.get("summary") or {}).get("medicines_confirmed"),
    }


def prescription_analytics(db: Session, *, limit: int = 40, compute_missing: bool = True) -> dict[str, Any]:
    """CER/WER/F1/BertScore only for real non-mock sessions with pharmacist confirmations."""
    sessions = db.scalars(
        select(ReviewSession).order_by(ReviewSession.updated_at.desc()).limit(min(limit * 5, 400))
    ).all()
    rows: list[dict[str, Any]] = []
    skipped = {"not_real": 0, "no_confirmations": 0, "unavailable": 0}

    for session in sessions:
        ok, _reason = _session_is_real(db, session)
        if not ok:
            skipped["not_real"] += 1
            continue
        owner = _owner(db, session)
        confirmed_n = (
            db.scalar(
                select(func.count())
                .select_from(PrescriptionMedicine)
                .where(
                    PrescriptionMedicine.session_id == session.id,
                    PrescriptionMedicine.pharmacist_status == "confirmed",
                )
            )
            or 0
        )
        if confirmed_n == 0:
            skipped["no_confirmations"] += 1
            continue

        # Prefer fresh compute for accuracy; fall back to cached only if compute fails
        payload = None
        if compute_missing:
            try:
                payload = compute_session_analytics(db, session)
            except Exception:  # noqa: BLE001
                payload = None
        if payload is None and session.analytics_json:
            try:
                payload = json.loads(session.analytics_json)
            except json.JSONDecodeError:
                payload = None
        if not payload or not payload.get("available"):
            skipped["unavailable"] += 1
            continue

        # Drop demo-labeled / unavailable bert placeholders from averages via nulls
        rows.append(
            _extract_prescription_metrics(
                payload, session, pharmacist_username=owner.username if owner else None
            )
        )
        if len(rows) >= limit:
            break

    def _nums(key: str) -> list[float]:
        out: list[float] = []
        for r in rows:
            v = r.get(key)
            if isinstance(v, (int, float)):
                out.append(float(v))
        return out

    return {
        "disclaimer": (
            "Live prescription-level metrics only. "
            "Includes self-registered pharmacists with non-mock OCR and at least one confirmed medicine. "
            "Averages are null when no qualifying sessions exist — values are never invented. "
            "CER/WER = full OCR vs pharmacist-accepted text; entity P/R/F1 uses normalized "
            "match (case/spacing/synonyms) so format-only diffs do not tank F1 — clinical "
            "changes (dose count, capsule vs tablet, 3× vs 4×) still count; "
            "BertScore = full prescription block when the package is enabled."
        ),
        "data_policy": {
            "exclude_seed_users": True,
            "exclude_test_usernames": True,
            "exclude_mock_ocr": True,
            "require_confirmations": True,
            "skipped": skipped,
        },
        "prescriptions_evaluated": len(rows),
        "averages": {
            "cer": _mean(_nums("cer")),
            "wer": _mean(_nums("wer")),
            "entity_precision": _mean(_nums("entity_precision")),
            "entity_recall": _mean(_nums("entity_recall")),
            "entity_f1": _mean(_nums("entity_f1")),
            "bertscore_precision": _mean(_nums("bertscore_precision")),
            "bertscore_recall": _mean(_nums("bertscore_recall")),
            "bertscore_f1": _mean(_nums("bertscore_f1")),
        },
        "prescriptions": rows,
    }
