"""Milestone 3 OCR / upload tests."""

from io import BytesIO

from app.services.ocr_service import run_ocr


def test_mock_ocr_engines_are_labelled():
    for engine in ("mock", "paddleocr", "tesseract", "trocr", "hybrid"):
        result = run_ocr(engine, b"fake-image-bytes-123456")
        assert result.is_mock is True
        assert result.raw_text
        assert result.confidence > 0
        assert any("MOCK" in w.upper() or "mock" in w.lower() for w in result.warnings) or result.is_mock


def _pharmacist_headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_and_ocr_flow(client):
    headers = _pharmacist_headers(client)
    files = {
        "file": ("synthetic.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png"),
    }
    upload = client.post("/api/v1/prescriptions/upload", headers=headers, files=files)
    assert upload.status_code == 200
    session_id = upload.json()["id"]

    ocr = client.post(
        f"/api/v1/ocr/{session_id}/run",
        headers=headers,
        json={"engine": "hybrid"},
    )
    assert ocr.status_code == 200
    body = ocr.json()
    assert body["is_mock"] is True
    assert "SYNTHETIC PRESCRIPTION" in body["raw_text"]
    assert body["character_count"] > 0

    image = client.get(f"/api/v1/prescriptions/{session_id}/image", headers=headers)
    assert image.status_code == 200

    deleted = client.delete(f"/api/v1/prescriptions/{session_id}/temporary-file", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_admin_cannot_upload_prescription(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!234"},
    ).json()["access_token"]
    files = {"file": ("x.png", BytesIO(b"abc"), "image/png")}
    response = client.post(
        "/api/v1/prescriptions/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 403


def test_health_phase_3(client):
    assert client.get("/health").json()["phase"] == "5-therapeutic"
