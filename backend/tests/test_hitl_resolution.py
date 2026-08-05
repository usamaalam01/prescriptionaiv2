"""P0/P1 HITL resolution and mock-confirm safety tests."""

from io import BytesIO


def _headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_unreadable_requires_reason_and_audits(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    headers = _headers(client)
    files = {"file": ("u.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    assert client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"}).status_code == 200
    meds = client.get(f"/api/v1/reviews/{session_id}/medicines", headers=headers).json()
    mid = meds[0]["id"]

    missing = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{mid}/verify",
        headers=headers,
        json={"status": "unidentified"},
    )
    assert missing.status_code == 422

    ok = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{mid}/verify",
        headers=headers,
        json={"status": "unidentified", "reason": "Handwriting illegible on this line"},
    )
    assert ok.status_code == 200
    assert ok.json()["pharmacist_status"] == "unidentified"

    audit = client.get(f"/api/v1/reviews/{session_id}/hitl-audit", headers=headers).json()
    assert any(e.get("event_type") == "hitl.row_unidentified" for e in audit.get("events") or [])


def test_pdf_upload_rejected(client):
    headers = _headers(client)
    files = {"file": ("rx.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    res = client.post("/api/v1/prescriptions/upload", headers=headers, files=files)
    assert res.status_code == 422
    assert "PDF" in str(res.json().get("detail", "")).upper()
