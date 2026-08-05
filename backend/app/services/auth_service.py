import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import UserStatus
from app.models.auth import LoginHistory, RefreshToken, User
from app.security.passwords import hash_password, validate_password_policy, verify_password
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
    token_hash,
)

GENERIC_LOGIN_ERROR = "Invalid username or password"
_LOGIN_ALLOWED_STATUSES = {
    UserStatus.ACTIVE.value,
    UserStatus.PENDING.value,
    UserStatus.PASSWORD_RESET_REQUIRED.value,
}


def _generate_temporary_password() -> str:
    """Strong one-time password that satisfies the shared password policy."""
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"Tmp!{body}"


def login(db: Session, username: str, password: str) -> tuple[str, str, User]:
    user = db.scalar(select(User).where(User.username == username))
    now = datetime.now(timezone.utc)

    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.status = UserStatus.LOCKED.value
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            db.add(LoginHistory(user_id=user.id, successful=False))
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    if user.status not in _LOGIN_ALLOWED_STATUSES or (
        user.status == UserStatus.ACTIVE.value and not user.is_active
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.add(LoginHistory(user_id=user.id, successful=True))

    session_id = str(__import__("uuid").uuid4())
    access = create_access_token(user_id=user.id, role=user.role, session_id=session_id)
    refresh, jti, family = create_refresh_token(user_id=user.id)
    payload = decode_token(refresh, "refresh")
    db.add(
        RefreshToken(
            id=jti,
            user_id=user.id,
            token_hash=token_hash(refresh),
            family_id=family,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()
    db.refresh(user)
    return access, refresh, user


def rotate_refresh(db: Session, raw_refresh: str) -> tuple[str, str, User]:
    try:
        payload = decode_token(raw_refresh, "refresh")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    record = db.get(RefreshToken, payload["jti"])
    if record is None or record.token_hash != token_hash(raw_refresh):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if record.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == record.family_id)
            .values(revoked_at=datetime.now(timezone.utc))
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if user.status == UserStatus.ACTIVE.value and not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if user.status not in _LOGIN_ALLOWED_STATUSES:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    record.revoked_at = datetime.now(timezone.utc)
    new_raw, new_jti, family = create_refresh_token(user_id=user.id, family_id=record.family_id)
    new_payload = decode_token(new_raw, "refresh")
    record.replaced_by_token_id = new_jti
    db.add(
        RefreshToken(
            id=new_jti,
            user_id=user.id,
            token_hash=token_hash(new_raw),
            family_id=family,
            expires_at=datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc),
        )
    )
    session_id = str(__import__("uuid").uuid4())
    access = create_access_token(user_id=user.id, role=user.role, session_id=session_id)
    db.commit()
    return access, new_raw, user


def logout(db: Session, raw_refresh: str) -> None:
    try:
        payload = decode_token(raw_refresh, "refresh")
    except Exception:
        return
    record = db.get(RefreshToken, payload["jti"])
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        db.commit()


def forgot_password(db: Session, username: str) -> str | None:
    """Issue a temporary password for an eligible account. Returns None if username unknown."""
    user = db.scalar(select(User).where(User.username == username.strip()))
    if user is None:
        return None
    if user.status == UserStatus.INACTIVE.value or not user.is_active:
        return None

    temporary = _generate_temporary_password()
    user.password_hash = hash_password(temporary)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None
    if user.status in {
        UserStatus.ACTIVE.value,
        UserStatus.LOCKED.value,
        UserStatus.PASSWORD_RESET_REQUIRED.value,
    }:
        user.status = UserStatus.PASSWORD_RESET_REQUIRED.value
    # Pending applicants keep pending so registration status UI still applies.

    now = datetime.now(timezone.utc)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    return temporary


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
) -> User:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if current_password == new_password:
        raise HTTPException(status_code=422, detail="New password must differ from the current password")
    validate_password_policy(new_password, username=user.username)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    if user.status == UserStatus.PASSWORD_RESET_REQUIRED.value:
        user.status = UserStatus.ACTIVE.value
    # Revoke all refresh tokens so other sessions must re-login
    now = datetime.now(timezone.utc)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    db.refresh(user)
    return user
