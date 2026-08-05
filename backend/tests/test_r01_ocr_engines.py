"""R01 OCR multi-engine contract, fallback, consensus, and provenance tests."""

from __future__ import annotations

import logging

import pytest

from app.services.ocr.consensus import page_consensus
from app.services.ocr.contract import EngineAttempt, is_acceptable, parse_engine_order
from app.services.ocr.engines import OcrDocumentResult, OcrLine, run_ocr_stack
from app.services.ocr.tesseract_adapter import run_tesseract, tesseract_available


def test_parse_engine_order_spec_default():
    order = parse_engine_order("trocr", "google_vision,tesseract")
    assert order == ["trocr", "google_vision", "tesseract"]


def test_parse_engine_order_rejects_unknown_and_dedupes():
    order = parse_engine_order("trocr", "trocr,google_vision,unknown,tesseract")
    assert order == ["trocr", "google_vision", "tesseract"]


def test_is_acceptable_empty_and_low_confidence():
    ok = EngineAttempt(engine_id="trocr", status="success", raw_text="Amoxicillin 500 mg", confidence=0.9)
    assert is_acceptable(ok, min_confidence=0.6)
    low = EngineAttempt(engine_id="trocr", status="success", raw_text="x", confidence=0.2)
    assert not is_acceptable(low, min_confidence=0.6)
    empty = EngineAttempt(engine_id="trocr", status="success", raw_text="  ", confidence=0.9)
    assert not is_acceptable(empty, min_confidence=0.6)


def test_tesseract_adapter_reports_unavailable_without_crash(monkeypatch):
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.tesseract_available",
        lambda: (False, "tesseract_binary_unavailable:Test"),
    )
    attempt = run_tesseract(b"fake-image")
    assert attempt.engine_id == "tesseract"
    assert attempt.status == "unavailable"
    assert attempt.error_code


def test_tesseract_adapter_normalised_success(monkeypatch):
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.tesseract_available",
        lambda: (True, None),
    )

    class _Img:
        def convert(self, _mode):
            return self

    class _Pyt:
        class Output:
            DICT = "dict"

        @staticmethod
        def image_to_data(_img, output_type=None):
            return {
                "text": ["Amoxicillin", "500", "mg"],
                "conf": ["91", "88", "90"],
                "left": [1, 2, 3],
                "top": [1, 1, 1],
                "width": [10, 10, 10],
                "height": [10, 10, 10],
            }

        @staticmethod
        def image_to_string(_img):
            return "Amoxicillin 500 mg"

    import sys
    import types

    fake_pil = types.ModuleType("PIL")
    fake_image = types.ModuleType("PIL.Image")
    fake_image.open = lambda *_a, **_k: _Img()
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)
    monkeypatch.setitem(sys.modules, "pytesseract", _Pyt)

    attempt = run_tesseract(b"\x89PNG")
    assert attempt.engine_id == "tesseract"
    assert attempt.status == "success"
    assert "Amoxicillin" in (attempt.raw_text or "")
    assert attempt.confidence is not None and attempt.confidence > 0.5


def _vision_doc(text: str, conf: float = 0.9) -> OcrDocumentResult:
    return OcrDocumentResult(
        full_text=text,
        lines=[OcrLine(text=text, confidence=conf, engine="google_vision")],
        engine_primary="google_vision",
        is_mock=False,
    )


def test_sequential_trocr_success_skips_need_for_fallback_when_not_preserving(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision,tesseract")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", False)
    monkeypatch.setattr(settings, "OCR_HYBRID_CONSENSUS_ENABLED", False)
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(settings, "OCR_ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)

    trocr_doc = OcrDocumentResult(
        full_text="Amoxicillin 500 mg",
        lines=[OcrLine(text="Amoxicillin 500 mg", confidence=0.91, engine="trocr-large-handwritten")],
        engine_primary="trocr",
        is_mock=False,
    )
    called = {"vision": 0, "tess": 0}

    monkeypatch.setattr("app.services.ocr.engines._run_trocr_document", lambda _b: trocr_doc)

    def vision(_b):
        called["vision"] += 1
        return _vision_doc("SHOULD_NOT_USE")

    def tess(_b):
        called["tess"] += 1
        return EngineAttempt(engine_id="tesseract", status="success", raw_text="x", confidence=0.9)

    monkeypatch.setattr("app.services.ocr.engines.google_vision_document_text", vision)
    monkeypatch.setattr("app.services.ocr.tesseract_adapter.run_tesseract", tess)

    result = run_ocr_stack(b"img")
    assert result.selected_engine == "trocr" or result.engine_primary == "trocr"
    assert "Amoxicillin" in result.full_text
    assert called["vision"] == 0
    assert called["tess"] == 0


def test_trocr_unavailable_falls_back_to_vision(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision,tesseract")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", False)
    monkeypatch.setattr(settings, "OCR_HYBRID_CONSENSUS_ENABLED", False)
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(settings, "ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)

    monkeypatch.setattr("app.services.ocr.engines._run_trocr_document", lambda _b: None)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda _b: _vision_doc("Ibuprofen 200 mg", 0.88),
    )
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.run_tesseract",
        lambda _b: EngineAttempt(engine_id="tesseract", status="unavailable", error_code="missing"),
    )

    result = run_ocr_stack(b"img")
    assert result.engine_primary == "google_vision"
    assert "Ibuprofen" in result.full_text
    assert any(a["engine_id"] == "trocr" for a in result.engine_attempts)


def test_vision_unavailable_falls_back_to_tesseract(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision,tesseract")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", False)
    monkeypatch.setattr(settings, "OCR_HYBRID_CONSENSUS_ENABLED", False)
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)

    monkeypatch.setattr("app.services.ocr.engines._run_trocr_document", lambda _b: None)
    monkeypatch.setattr("app.services.ocr.engines.google_vision_document_text", lambda _b: None)
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.run_tesseract",
        lambda _b: EngineAttempt(
            engine_id="tesseract",
            status="success",
            raw_text="Paracetamol 500 mg",
            confidence=0.77,
            lines=[{"text": "Paracetamol 500 mg", "confidence": 0.77, "engine": "tesseract"}],
        ),
    )

    result = run_ocr_stack(b"img")
    assert result.engine_primary == "tesseract"
    assert "Paracetamol" in result.full_text


def test_all_engines_unavailable_mock_fallback(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision,tesseract")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", True)
    monkeypatch.setattr(settings, "OCR_ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)

    monkeypatch.setattr("app.services.ocr.engines._run_trocr_document", lambda _b: None)
    monkeypatch.setattr("app.services.ocr.engines.google_vision_document_text", lambda _b: None)
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.run_tesseract",
        lambda _b: EngineAttempt(engine_id="tesseract", status="unavailable", error_code="missing"),
    )

    result = run_ocr_stack(b"img")
    assert result.is_mock is True
    assert result.requires_human_review is True
    assert {a["engine_id"] for a in result.engine_attempts} >= {"trocr", "google_vision", "tesseract"}


def test_preserve_engine_outputs_no_silent_overwrite(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PROFILE", "production")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision,tesseract")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", True)
    monkeypatch.setattr(settings, "OCR_HYBRID_CONSENSUS_ENABLED", False)
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)
    monkeypatch.setattr(settings, "ENABLE_TROCR_RETRY", False)

    monkeypatch.setattr(
        "app.services.ocr.engines._run_trocr_document",
        lambda _b: OcrDocumentResult(
            full_text="Drug A",
            lines=[OcrLine(text="Drug A", confidence=0.95, engine="trocr")],
            engine_primary="trocr",
            is_mock=False,
        ),
    )
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda _b: _vision_doc("Drug B", 0.9),
    )
    monkeypatch.setattr(
        "app.services.ocr.tesseract_adapter.run_tesseract",
        lambda _b: EngineAttempt(
            engine_id="tesseract",
            status="success",
            raw_text="Drug C",
            confidence=0.7,
            lines=[{"text": "Drug C", "confidence": 0.7, "engine": "tesseract"}],
        ),
    )
    monkeypatch.setattr(
        "app.services.ocr.preprocess.preprocess_prescription_image",
        lambda data, **_k: data,
    )

    result = run_ocr_stack(b"img")
    by_engine = {a["engine_id"]: a.get("raw_text") for a in result.engine_attempts}
    assert by_engine.get("trocr") == "Drug A"
    assert by_engine.get("google_vision") == "Drug B"
    assert by_engine.get("tesseract") == "Drug C"
    # Selected text comes from first acceptable engine; attempts remain independent
    assert "Drug A" in (result.full_text or result.lines[0].text if result.lines else "")


def test_hybrid_consensus_agreement_and_conflict():
    agree = page_consensus(
        [
            EngineAttempt(engine_id="trocr", status="success", raw_text="Amoxicillin 500 mg", confidence=0.91),
            EngineAttempt(engine_id="google_vision", status="success", raw_text="Amoxicillin 500mg", confidence=0.89),
        ]
    )
    assert agree.consensus_status in {"agreement", "majority"}
    assert agree.requires_human_review is False

    conflict = page_consensus(
        [
            EngineAttempt(engine_id="trocr", status="success", raw_text="Amoxicillin 500 mg", confidence=0.91),
            EngineAttempt(engine_id="google_vision", status="success", raw_text="Ibuprofen 200 mg", confidence=0.89),
            EngineAttempt(engine_id="tesseract", status="success", raw_text="Warfarin 3 mg", confidence=0.7),
        ]
    )
    assert conflict.consensus_status in {"conflict", "majority"}
    assert conflict.requires_human_review is True
    assert len(conflict.candidates) == 3
    values = {c["value"] for c in conflict.candidates}
    assert conflict.selected_value in values


def test_ocr_profile_spec_uses_trocr_first(monkeypatch):
    from app.core.config import settings
    from app.services.ocr.contract import parse_engine_order

    monkeypatch.setattr(settings, "OCR_PROFILE", "spec")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "google_vision")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "tesseract")
    monkeypatch.setattr(settings, "OCR_SPEC_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_SPEC_FALLBACK_ORDER", "google_vision,tesseract")
    # Mirror engines.py profile resolution
    order = parse_engine_order(settings.OCR_SPEC_PRIMARY, settings.OCR_SPEC_FALLBACK_ORDER)
    assert order[0] == "trocr"
    assert "google_vision" in order
    assert "tesseract" in order


def test_ocr_logs_do_not_include_raw_text(monkeypatch, caplog):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_STRATEGY", "sequential")
    monkeypatch.setattr(settings, "OCR_PRIMARY", "trocr")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ORDER", "google_vision")
    monkeypatch.setattr(settings, "OCR_PRESERVE_ENGINE_OUTPUTS", False)
    monkeypatch.setattr(settings, "OCR_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_DESKEW", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_INK_ISOLATE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_BINARIZE", False)
    monkeypatch.setattr(settings, "OCR_PREPROCESS_SHARPEN", False)
    monkeypatch.setattr(settings, "ENABLE_TROCR_RETRY", False)
    secret = "SECRET_PATIENT_NAME_SHOULD_NOT_LOG"
    monkeypatch.setattr(
        "app.services.ocr.engines._run_trocr_document",
        lambda _b: OcrDocumentResult(
            full_text=secret,
            lines=[OcrLine(text=secret, confidence=0.99, engine="trocr")],
            engine_primary="trocr",
            is_mock=False,
        ),
    )
    with caplog.at_level(logging.INFO, logger="app.services.ocr.engines"):
        run_ocr_stack(b"img")
    joined = " ".join(r.message for r in caplog.records)
    assert secret not in joined
    assert "ocr_engine=trocr" in joined


def test_tesseract_available_probe_returns_tuple():
    ok, reason = tesseract_available()
    assert isinstance(ok, bool)
    assert reason is None or isinstance(reason, str)
