"""OCR adapters for Milestone 3.

Real engines (PaddleOCR, Tesseract, TrOCR, Google Vision) are not required yet.
Each adapter returns clearly labelled MOCK results so academic demos stay honest.
Replace a mock class with a real implementation behind the same interface later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class OcrResult:
    engine: str
    raw_text: str
    confidence: float
    processing_ms: int
    is_mock: bool
    warnings: list[str]


class OcrEngine:
    name: str

    def run(self, image_bytes: bytes) -> OcrResult:  # noqa: ARG002
        raise NotImplementedError


MOCK_PRESCRIPTION_TEXT = """SYNTHETIC PRESCRIPTION — NO REAL PATIENT DATA

Prescriber: Dr. A. Example  Reg: EX-0001
Clinic: Academic Demo Clinic
Date: 13 April 2026

Patient ref: ANON-1001  Age: 45  Sex: F

1. Arcabose 50 mg tablets
   Take ONE tablet THREE times daily with meals
   Route: Oral

2. Pantoprazole 40 mg tablets
   Take ONE tablet ONCE daily before breakfast
   Route: Oral

3. Cetirizine 10 mg tablets
   Take ONE tablet ONCE daily
   Route: Oral

4. Acetaminophen 500 mg tablets
   Take TWO tablets every 6 hours as required
   Route: Oral

Clinical note: Synthetic sample for CSCK700 PharmaAssist evaluation only.
"""


class MockOcrEngine(OcrEngine):
    name = "mock"

    def run(self, image_bytes: bytes) -> OcrResult:
        started = time.perf_counter()
        # Tiny deterministic variation from file size so outputs are not identical across engines
        noise = len(image_bytes) % 7
        text = MOCK_PRESCRIPTION_TEXT + f"\n[mock-engine marker bytes={len(image_bytes)} noise={noise}]"
        elapsed = int((time.perf_counter() - started) * 1000)
        return OcrResult(
            engine=self.name,
            raw_text=text,
            confidence=0.82,
            processing_ms=max(elapsed, 1),
            is_mock=True,
            warnings=["MOCK OCR: replace with PaddleOCR/Tesseract/TrOCR adapter when available."],
        )


class MockPaddleEngine(MockOcrEngine):
    name = "paddleocr"

    def run(self, image_bytes: bytes) -> OcrResult:
        result = super().run(image_bytes)
        result.engine = self.name
        result.confidence = 0.88
        result.warnings = ["MOCK PaddleOCR adapter — not the real PaddleOCR runtime."]
        return result


class MockTesseractEngine(MockOcrEngine):
    name = "tesseract"

    def run(self, image_bytes: bytes) -> OcrResult:
        result = super().run(image_bytes)
        result.engine = self.name
        result.confidence = 0.74
        result.raw_text = result.raw_text.replace("Amoxicillin", "Amoxycillin")  # intentional OCR-like variant
        result.warnings = ["MOCK Tesseract adapter — not the real Tesseract binary."]
        return result


class MockTrocrEngine(MockOcrEngine):
    name = "trocr"

    def run(self, image_bytes: bytes) -> OcrResult:
        result = super().run(image_bytes)
        result.engine = self.name
        result.confidence = 0.79
        result.warnings = ["MOCK TrOCR adapter — not a transformer model."]
        return result


class HybridMockEngine(OcrEngine):
    name = "hybrid"

    def __init__(self) -> None:
        self.engines = [MockPaddleEngine(), MockTesseractEngine(), MockTrocrEngine()]

    def run(self, image_bytes: bytes) -> OcrResult:
        started = time.perf_counter()
        results = [engine.run(image_bytes) for engine in self.engines]
        # Confidence-weighted pick of the highest-confidence engine text
        best = max(results, key=lambda item: item.confidence)
        elapsed = int((time.perf_counter() - started) * 1000)
        conflict = len({item.raw_text for item in results}) > 1
        warnings = [
            "MOCK Hybrid OCR consensus — engines are mocked.",
            f"Selected engine text from {best.engine} (confidence={best.confidence:.2f}).",
        ]
        if conflict:
            warnings.append("Conflicting mock engine outputs detected; pharmacist review required.")
        return OcrResult(
            engine=self.name,
            raw_text=best.raw_text,
            confidence=sum(r.confidence for r in results) / len(results),
            processing_ms=max(elapsed, 1),
            is_mock=True,
            warnings=warnings,
        )


ENGINES: dict[str, OcrEngine] = {
    "mock": MockOcrEngine(),
    "paddleocr": MockPaddleEngine(),
    "tesseract": MockTesseractEngine(),
    "trocr": MockTrocrEngine(),
    "hybrid": HybridMockEngine(),
}


def run_ocr(engine_name: str, image_bytes: bytes) -> OcrResult:
    engine = ENGINES.get(engine_name)
    if engine is None:
        raise ValueError(f"Unsupported OCR engine: {engine_name}")
    return engine.run(image_bytes)
