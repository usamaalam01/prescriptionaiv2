"""Map OCR lines to top-3 medicine candidates from the real catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.datasets.match import DISCLAIMER, suggest_medicines
from app.services.datasets.catalog_store import catalog_available
from app.services.ocr.engines import OcrDocumentResult, run_ocr_stack


@dataclass
class MedicineCandidateBundle:
    ocr_line: str
    ocr_confidence: float
    candidates: list[dict] = field(default_factory=list)


@dataclass
class PharmaOcrValidationResult:
    disclaimer: str
    catalog_ready: bool
    ocr: dict
    medicines: list[MedicineCandidateBundle]
    warnings: list[str] = field(default_factory=list)


def validate_prescription_image(image_bytes: bytes) -> PharmaOcrValidationResult:
    ocr = run_ocr_stack(image_bytes)
    ready = catalog_available()
    medicines: list[MedicineCandidateBundle] = []
    warnings = list(ocr.warnings)
    if not ready:
        warnings.append(
            "Medicine catalog SQLite not built. Run: python -m app.services.datasets.build_index"
        )

    for line in ocr.lines:
        text = line.text.strip()
        if len(text) < 3:
            continue
        # Skip obvious non-medicine headers
        low = text.lower()
        if low.startswith(("patient", "age", "date", "dr ", "doctor", "rx")):
            continue
        hits = suggest_medicines(text, top_k=3) if ready else []
        medicines.append(
            MedicineCandidateBundle(
                ocr_line=text,
                ocr_confidence=line.confidence,
                candidates=[asdict(h) for h in hits],
            )
        )

    return PharmaOcrValidationResult(
        disclaimer=DISCLAIMER,
        catalog_ready=ready,
        ocr={
            "engine_primary": ocr.engine_primary,
            "is_mock": ocr.is_mock,
            "full_text": ocr.full_text,
            "line_count": len(ocr.lines),
        },
        medicines=medicines,
        warnings=warnings,
    )
