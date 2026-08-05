from fastapi import APIRouter, Depends

from app.models.auth import User
from app.security.rbac import require_administrator, require_pharmacist, require_reviewer

router = APIRouter(prefix="/rbac", tags=["rbac-check"])


@router.get("/administrator")
def admin_ping(user: User = Depends(require_administrator)):
    return {"ok": True, "role": user.role, "username": user.username}


@router.get("/pharmacist")
def pharmacist_ping(user: User = Depends(require_pharmacist)):
    return {"ok": True, "role": user.role, "username": user.username}


@router.get("/reviewer")
def reviewer_ping(user: User = Depends(require_reviewer)):
    return {"ok": True, "role": user.role, "username": user.username}
