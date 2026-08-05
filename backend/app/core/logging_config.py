"""Structured logging setup for award-path / production operations."""

from __future__ import annotations

import logging
import sys
from typing import Any


class _KeyValueFormatter(logging.Formatter):
    """Compact key=value lines (easy to grep; JSON-friendly enough for demos)."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: list[str] = []
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "user_id"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        if extras:
            return f"{base} {' '.join(extras)}"
        return base


def configure_logging(*, level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_pharmaassist_configured", False):
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _KeyValueFormatter(
            fmt="%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.handlers.clear()
    root.addHandler(handler)
    # Quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    root._pharmaassist_configured = True  # type: ignore[attr-defined]


def bind_extra(logger: logging.Logger, **kwargs: Any) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logger, kwargs)
