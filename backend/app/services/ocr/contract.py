"""Common OCR engine result contract (R01). No silent overwrite across engines."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EngineAttempt:
    """Normalized per-engine attempt — retained independently of the selected result."""

    engine_id: str
    status: str  # success | empty | low_confidence | unavailable | error
    raw_text: str | None = None
    confidence: float | None = None
    processing_ms: float | None = None
    error_code: str | None = None
    warning: str | None = None
    is_mock: bool = False
    lines: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_acceptable(
    attempt: EngineAttempt,
    *,
    min_confidence: float,
) -> bool:
    if attempt.status != "success":
        return False
    if not (attempt.raw_text or "").strip():
        return False
    if attempt.confidence is None:
        return True
    return float(attempt.confidence) >= float(min_confidence)


def parse_engine_order(primary: str, fallback_csv: str) -> list[str]:
    """Deduplicate while preserving Spec order: primary then fallbacks."""
    allowed = {"trocr", "google_vision", "tesseract", "paddle", "paddleocr"}
    ordered: list[str] = []
    for raw in [primary, *[p.strip() for p in (fallback_csv or "").split(",")]]:
        name = (raw or "").strip().lower()
        if name == "paddleocr":
            name = "paddle"
        if not name or name not in allowed:
            continue
        if name not in ordered:
            ordered.append(name)
    return ordered or ["trocr", "google_vision", "tesseract"]
