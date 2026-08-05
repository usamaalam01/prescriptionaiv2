"""Independent OCR engine adapters for DQ1 evaluation (do not overwrite each other)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass
class OcrEngineResult:
    engine_id: str
    engine_version: str
    raw_text: str | None
    structured_fields: dict[str, Any]
    field_confidence: dict[str, float]
    processing_time_ms: float
    preprocessing_configuration: dict[str, Any]
    error_status: str | None = None


def _timed(fn: Callable[[], tuple[str | None, dict[str, Any], dict[str, float]]]) -> OcrEngineResult:
    raise NotImplementedError


def run_engine(
    engine_id: str,
    *,
    engine_version: str = "eval-1",
    raw_text: str | None = None,
    structured_fields: dict[str, Any] | None = None,
    field_confidence: dict[str, float] | None = None,
    preprocessing: dict[str, Any] | None = None,
    error_status: str | None = None,
    processing_time_ms: float | None = None,
) -> dict[str, Any]:
    """Build a common OCR result schema; engines never share mutable state."""
    t0 = time.perf_counter()
    if processing_time_ms is None:
        processing_time_ms = (time.perf_counter() - t0) * 1000.0
    result = OcrEngineResult(
        engine_id=engine_id,
        engine_version=engine_version,
        raw_text=raw_text,
        structured_fields=dict(structured_fields or {}),
        field_confidence=dict(field_confidence or {}),
        processing_time_ms=float(processing_time_ms),
        preprocessing_configuration=dict(preprocessing or {}),
        error_status=error_status,
    )
    return asdict(result)


def simulate_engine_outputs(
    *,
    ground_truth_text: str,
    ground_truth_fields: dict[str, Any],
    noise_by_engine: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    For offline/synthetic evaluation when live engines are unavailable.
    Each engine gets an independent copy of fields with optional character noise.
    Production Vision remains primary in the live app; this is reviewer-only eval.
    """
    noise = noise_by_engine or {
        "trocr": 0.05,
        "google_vision": 0.02,
        "hybrid": 0.03,
        "paddleocr": 0.08,
        "tesseract": 0.12,
    }
    out: dict[str, dict[str, Any]] = {}
    for engine_id, rate in noise.items():
        hyp_text = _apply_char_noise(ground_truth_text, rate, seed=hash(engine_id) & 0xFFFF)
        hyp_fields = {k: _apply_char_noise(str(v or ""), rate, seed=hash(engine_id + k) & 0xFFFF) for k, v in ground_truth_fields.items()}
        out[engine_id] = run_engine(
            engine_id,
            engine_version="sim-1",
            raw_text=hyp_text,
            structured_fields=hyp_fields,
            field_confidence={k: max(0.0, 1.0 - rate) for k in hyp_fields},
            preprocessing={"mode": "synthetic_eval"},
            processing_time_ms=10.0 + rate * 100,
        )
    return out


def _apply_char_noise(text: str, rate: float, seed: int) -> str:
    if not text or rate <= 0:
        return text
    import random

    rng = random.Random(seed)
    chars = list(text)
    for i in range(len(chars)):
        if rng.random() < rate and chars[i].isalnum():
            chars[i] = rng.choice("abcdefghijklmnopqrstuvwxyz0123456789")
    return "".join(chars)


CONFIGURED_ENGINES = ("trocr", "google_vision", "hybrid", "paddleocr", "tesseract")

# Thesis roles for reviewer DQ1 dashboard (production HITL stays Vision-primary).
ENGINE_THESIS_ROLES: dict[str, dict[str, str]] = {
    "trocr": {
        "label": "TrOCR",
        "thesis_role": "Spec-named DQ1 engine",
        "operational_role": "Optional crop retry in production HITL",
    },
    "google_vision": {
        "label": "Google Vision",
        "thesis_role": "Production primary recogniser (HITL path)",
        "operational_role": "Live Analyzer / Confirm OCR",
    },
    "hybrid": {
        "label": "Hybrid / production path",
        "thesis_role": "What pharmacists use (Vision ± TrOCR retry)",
        "operational_role": "Merged production stack proxy for evaluation",
    },
    "paddleocr": {
        "label": "PaddleOCR",
        "thesis_role": "Optional line-detection assist",
        "operational_role": "Detection only when ENABLE_PADDLE_DETECT",
    },
    "tesseract": {
        "label": "Tesseract",
        "thesis_role": "Spec final / local fallback",
        "operational_role": "Offline fallback when configured",
    },
}

DQ1_RESEARCH_QUESTION = (
    "How accurately does the PharmaAssist OCR pipeline (and each configured engine, including TrOCR) "
    "extract medicine names and dosages from synthetic handwritten prescriptions, measured by WER and CER "
    "against pharmacist-confirmed ground truth?"
)

DQ1_SPEC_QUESTION = (
    "Spec DQ1 (approved wording): How accurately does TrOCR extract drug names and dosages? (WER/CER). "
    "TrOCR is reported as the Spec-named arm; other engines are compared honestly under the same ground truth."
)
