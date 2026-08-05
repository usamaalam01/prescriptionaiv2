"""Fail-closed checks for production-grade deployments."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_WEAK_JWT = {
    "dev-only-change-me-jwt-secret-key-32chars",
    "changeme",
    "secret",
    "password",
}
_WEAK_FIELD_KEYS = {
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
}


def validate_runtime_settings() -> list[str]:
    """Return warnings (development) or raise RuntimeError (production)."""
    issues: list[str] = []
    env = (settings.APP_ENV or "development").lower()
    is_prod = env in {"production", "prod", "staging"}

    if settings.JWT_SECRET_KEY in _WEAK_JWT or len(settings.JWT_SECRET_KEY) < 32:
        issues.append("JWT_SECRET_KEY is weak or default — set a unique secret (>=32 chars).")
    if settings.FIELD_ENCRYPTION_KEY in _WEAK_FIELD_KEYS:
        issues.append("FIELD_ENCRYPTION_KEY is the documented placeholder — generate a real key.")
    if is_prod and settings.APP_DEBUG:
        issues.append("APP_DEBUG must be false in production/staging.")
    if is_prod and settings.OCR_ALLOW_MOCK_FALLBACK:
        issues.append("OCR_ALLOW_MOCK_FALLBACK must be false in production/staging.")
    if is_prod and settings.OCR_PRIMARY == "google_vision":
        if not (settings.GOOGLE_VISION_API_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS):
            issues.append("Google Vision credentials required when OCR_PRIMARY=google_vision.")
    if is_prod and "google_vision" in (settings.OCR_FALLBACK_ORDER or ""):
        if not (settings.GOOGLE_VISION_API_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS):
            issues.append(
                "Google Vision credentials recommended when google_vision is in OCR_FALLBACK_ORDER."
            )

    if is_prod and issues:
        raise RuntimeError("Production settings invalid:\n- " + "\n- ".join(issues))

    for msg in issues:
        logger.warning("Settings warning: %s", msg)
    return issues
