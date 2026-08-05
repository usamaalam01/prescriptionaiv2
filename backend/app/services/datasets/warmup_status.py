"""Process-wide medicine-catalog warmup status (API lifespan thread)."""

from __future__ import annotations

from typing import Any

_warmup: dict[str, Any] = {
    "status": "pending",  # pending | ready | skipped | failed
    "aliases": None,
    "seconds": None,
    "error": None,
}


def set_warmup_status(
    status: str,
    *,
    aliases: int | None = None,
    seconds: float | None = None,
    error: str | None = None,
) -> None:
    _warmup["status"] = status
    if aliases is not None:
        _warmup["aliases"] = aliases
    if seconds is not None:
        _warmup["seconds"] = round(float(seconds), 2)
    if error is not None:
        _warmup["error"] = error


def get_warmup_status() -> dict[str, Any]:
    return dict(_warmup)
