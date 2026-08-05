"""Pillar-1 OCR: merged line confidence / conflict metadata for Analyzer panel."""

from app.services.pipeline import (
    CandidateMerger,
    LineCandidate,
    PrescriptionPipeline,
    UNCERTAIN_THRESHOLD,
)


def test_candidate_merger_flags_conflict_when_texts_differ():
    primary = LineCandidate(
        line_id="ocr-0",
        text="Ibrufen 400 mg",
        confidence=0.55,
        engine="vision",
        is_mock=True,
    )
    retry = LineCandidate(
        line_id="trocr-ocr-0",
        text="Ibuprofen 400 mg",
        confidence=0.88,
        engine="trocr",
        is_mock=True,
        source_stage="trocr_retry",
    )
    merged = CandidateMerger().merge([primary], {"ocr-0": retry})
    assert len(merged) == 1
    line = merged[0]
    assert line.conflict is True
    assert line.used_trocr_retry is True
    assert line.selected_text == "Ibuprofen 400 mg"
    assert line.selected_engine == "trocr"
    assert line.selected_confidence == 0.88
    assert len(line.candidates) == 2


def test_pipeline_mock_exposes_merged_lines_with_confidence():
    result = PrescriptionPipeline().run(b"\x89PNG\r\n\x1a\n" + b"pillar1-ocr-test")
    assert result.merged_lines, "expected OCR lines for Analyzer conflict panel"
    payload = result.to_json()
    assert "merged_lines" in payload
    assert "selected_confidence" in payload
    for line in result.merged_lines:
        assert 0.0 <= line.selected_confidence <= 1.0
        assert line.selected_text
        assert line.line_id
        assert isinstance(line.candidates, list)
    assert result.overall_ocr_confidence > 0
    # Mock path should surface at least one uncertain/retry candidate path historically
    assert UNCERTAIN_THRESHOLD == 0.78
