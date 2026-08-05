from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import RegistrationStatus, UserStatus
from app.models.admin import RegistrationDecision, RegistrationRequest
from app.models.auth import User


def decide_registration(
    db: Session,
    admin: User,
    request_id: str,
    *,
    approve: bool,
    confirmed_role: str = "pharmacist",
    reason: str | None = None,
) -> RegistrationRequest:
    request = db.get(RegistrationRequest, request_id)
    if not request or request.status != RegistrationStatus.PENDING_REVIEW.value:
        raise HTTPException(status_code=404, detail="Pending registration not found")

    user = db.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if approve:
        role = confirmed_role if confirmed_role in {"pharmacist", "reviewer"} else "pharmacist"
        request.status = RegistrationStatus.APPROVED.value
        user.status = UserStatus.ACTIVE.value
        user.is_active = True
        user.role = role
        decision = "approved"
    else:
        request.status = RegistrationStatus.REJECTED.value
        user.status = UserStatus.INACTIVE.value
        user.is_active = False
        role = user.role
        decision = "rejected"

    request.reviewed_at = datetime.now(timezone.utc)
    db.add(
        RegistrationDecision(
            registration_id=request.id,
            administrator_id=admin.id,
            decision=decision,
            confirmed_role=role,
            reason=reason,
        )
    )
    db.commit()
    db.refresh(request)
    return request
