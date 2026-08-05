from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from fastapi import HTTPException

from app.core.config import settings

_hasher = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
)

_WEAK_SUBSTRINGS = (
    "password",
    "123456",
    "pharmaassist",
    "liverpool",
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def validate_password_policy(password: str, *, username: str) -> None:
    """Shared password rules for registration and change-password."""
    if len(password) < 12:
        raise HTTPException(status_code=422, detail="New password must be at least 12 characters")
    if password.lower() == username.lower():
        raise HTTPException(status_code=422, detail="New password must not match the username")
    lowered = password.lower()
    if any(s in lowered for s in _WEAK_SUBSTRINGS):
        raise HTTPException(
            status_code=422,
            detail="New password is too weak — avoid common words like password / 123456",
        )
    classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes < 3:
        raise HTTPException(
            status_code=422,
            detail="New password needs at least 3 of: lower, upper, digit, symbol",
        )
