from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import client_key, limiter
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.security.rbac import get_current_user
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    limiter.check(client_key(request, "login"), limit=20, window_seconds=60)
    access, refresh, user = auth_service.login(db, body.username, body.password)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    limiter.check(client_key(request, "refresh"), limit=60, window_seconds=60)
    access, refresh_token, user = auth_service.rotate_refresh(db, body.refresh_token)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    auth_service.logout(db, body.refresh_token)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Self-service reset for the academic prototype (no email delivery)."""
    limiter.check(client_key(request, "forgot-password"), limit=8, window_seconds=300)
    temporary = auth_service.forgot_password(db, body.username)
    if temporary is None:
        return ForgotPasswordResponse(
            message=(
                "If that username exists, a temporary password would be shown here. "
                "Check the username or contact an administrator."
            ),
            temporary_password=None,
        )
    return ForgotPasswordResponse(
        message=(
            "A temporary password was issued. Sign in with it, then choose a new password. "
            "This value is shown once (prototype has no email)."
        ),
        temporary_password=temporary,
    )


@router.post("/change-password", response_model=UserOut)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Forced / voluntary password change for seed and reset accounts."""
    limiter.check(client_key(request, "change-password"), limit=10, window_seconds=300)
    updated = auth_service.change_password(
        db,
        user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return UserOut.model_validate(updated)
