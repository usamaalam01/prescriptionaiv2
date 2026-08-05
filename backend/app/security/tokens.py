import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: str, role: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "sid": session_id,
        "typ": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: str, family_id: str | None = None) -> tuple[str, str, str]:
    """Return raw_token, jti, family_id."""
    now = datetime.now(timezone.utc)
    family = family_id or str(uuid.uuid4())
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "family": family,
        "typ": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    raw = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return raw, jti, family


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("Invalid token type")
    return payload
