"""Tesseract OCR adapter behind the common OCR contract (R01)."""

from __future__ import annotations

import io
import logging
import time
from typing import Any

from app.services.ocr.contract import EngineAttempt

logger = logging.getLogger(__name__)


def tesseract_available() -> tuple[bool, str | None]:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return False, f"pytesseract_or_pillow_missing:{type(exc).__name__}"
    try:
        # Avoid shell injection: only probe binary; no user input.
        pytesseract.get_tesseract_version()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"tesseract_binary_unavailable:{type(exc).__name__}"


def run_tesseract(image_bytes: bytes) -> EngineAttempt:
    """Run Tesseract on image bytes. Never logs raw OCR text."""
    t0 = time.perf_counter()
    ok, reason = tesseract_available()
    if not ok:
        logger.info("ocr_engine=tesseract status=unavailable reason=%s", reason)
        return EngineAttempt(
            engine_id="tesseract",
            status="unavailable",
            error_code=reason or "unavailable",
            processing_ms=(time.perf_counter() - t0) * 1000.0,
            warning="Tesseract not installed or not on PATH; Spec final fallback unavailable.",
        )
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        data: dict[str, Any] = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        texts: list[str] = []
        confs: list[float] = []
        lines_out: list[dict[str, Any]] = []
        n = len(data.get("text") or [])
        for i in range(n):
            tok = (data["text"][i] or "").strip()
            if not tok:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:  # noqa: BLE001
                conf = -1.0
            if conf < 0:
                continue
            texts.append(tok)
            confs.append(conf / 100.0)
            lines_out.append(
                {
                    "text": tok,
                    "confidence": conf / 100.0,
                    "engine": "tesseract",
                    "bbox": [
                        float(data["left"][i]),
                        float(data["top"][i]),
                        float(data["left"][i] + data["width"][i]),
                        float(data["top"][i] + data["height"][i]),
                    ],
                }
            )
        raw = " ".join(texts).strip()
        # Prefer line-grouped text when available
        try:
            raw_lines = pytesseract.image_to_string(img) or ""
            if raw_lines.strip():
                raw = raw_lines.strip()
        except Exception:  # noqa: BLE001
            pass
        elapsed = (time.perf_counter() - t0) * 1000.0
        if not raw:
            logger.info("ocr_engine=tesseract status=empty ms=%.1f", elapsed)
            return EngineAttempt(
                engine_id="tesseract",
                status="empty",
                raw_text="",
                confidence=0.0,
                processing_ms=elapsed,
                lines=lines_out,
            )
        mean_conf = sum(confs) / len(confs) if confs else 0.5
        logger.info("ocr_engine=tesseract status=success ms=%.1f conf=%.3f", elapsed, mean_conf)
        return EngineAttempt(
            engine_id="tesseract",
            status="success",
            raw_text=raw,
            confidence=float(mean_conf),
            processing_ms=elapsed,
            lines=lines_out
            or [{"text": ln, "confidence": mean_conf, "engine": "tesseract"} for ln in raw.splitlines() if ln.strip()],
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000.0
        logger.warning("ocr_engine=tesseract status=error type=%s ms=%.1f", type(exc).__name__, elapsed)
        return EngineAttempt(
            engine_id="tesseract",
            status="error",
            error_code=type(exc).__name__,
            processing_ms=elapsed,
            warning="Tesseract execution failed.",
        )
