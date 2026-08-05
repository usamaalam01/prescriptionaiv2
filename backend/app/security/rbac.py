from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.db.session import get_db
from app.models.auth import User
from app.security.tokens import decode_token

bearer = HTTPBearer(auto_error=False)

AUTHENTICATABLE = {
    UserStatus.ACTIVE.value,
    UserStatus.PENDING.value,
    UserStatus.PASSWORD_RESET_REQUIRED.value,
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials, "access")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated") from exc

    user = db.get(User, payload["sub"])
    if user is None or user.status not in AUTHENTICATABLE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.status == UserStatus.ACTIVE.value and not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_roles(*roles: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.status != UserStatus.ACTIVE.value or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dependency


require_administrator = require_roles("administrator")
require_pharmacist = require_roles("pharmacist")
require_reviewer = require_roles("reviewer")
