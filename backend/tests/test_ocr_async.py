"""OCR async queue helpers (unit-level, no Vision call)."""

from app.services import prescription_service


def test_enqueue_and_get_job_helpers_exist():
    assert callable(prescription_service.enqueue_session_pipeline)
    assert callable(prescription_service.execute_queued_pipeline)
    assert callable(prescription_service.get_ocr_job_for_pharmacist)
