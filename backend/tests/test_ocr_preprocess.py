"""OCR preprocess best-practice smoke tests (no network)."""

from pathlib import Path

from app.services.ocr.preprocess import preprocess_prescription_image, preprocess_status


def test_preprocess_status_reports_libs():
    status = preprocess_status()
    assert status["pillow"] is True
    # numpy/opencv installed for this environment
    assert status["numpy"] is True
    assert status["opencv"] is True


def test_preprocess_curated_handwritten_rx_returns_png():
    img = Path(r"D:\Projects\PharmaAssist\data\test_prescriptions\curated_hitl_test_rx.png")
    assert img.exists()
    out = preprocess_prescription_image(
        img.read_bytes(),
        deskew=True,
        ink_isolate=True,
        adaptive_binarize=True,
        sharpen=True,
        max_side=1600,
    )
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(out) > 1000
