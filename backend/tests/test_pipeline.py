"""Pipeline stage tests for Milestone 3 multi-engine flow."""

from io import BytesIO

from app.services.pipeline import PrescriptionPipeline, UNCERTAIN_THRESHOLD


def test_pipeline_runs_all_stages():
    result = PrescriptionPipeline().run(b"synthetic-image-bytes-1234567890")
    assert "ocr_stack_spec_sequential" in result.stages_used
    assert "medical_parser" in result.stages_used
    assert "catalog_formulary_validation" in result.stages_used
    assert result.parsed_medicines
    assert result.formulary_checks
    assert any(line.confidence < UNCERTAIN_THRESHOLD for line in result.paddle_lines)
    assert result.trocr_retries
    assert any(m.medicine_name == "Pantoprazole" for m in result.parsed_medicines)


def test_formulary_match_for_seed_medicines():
    result = PrescriptionPipeline().run(b"x" * 40)
    matched = [c for c in result.formulary_checks if c.matched]
    # Pantoprazole / Cetirizine / Acetaminophen exact; Arcabose intentionally unmatched until HITL
    assert len(matched) >= 2
    assert any(m.medicine_name == "Arcabose" for m in result.parsed_medicines)


def _pharmacist_headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pipeline_api_and_pharmacist_verify(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    headers = _pharmacist_headers(client)
    files = {"file": ("synthetic.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"1" * 80), "image/png")}
    upload = client.post("/api/v1/prescriptions/upload", headers=headers, files=files)
    assert upload.status_code == 200
    session_id = upload.json()["id"]

    run = client.post(
        f"/api/v1/ocr/{session_id}/run",
        headers=headers,
        json={"engine": "pipeline"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["engine"] == "pipeline"
    assert body["pipeline"] is not None
    assert "stages_used" in body["pipeline"]

    meds = client.get(f"/api/v1/reviews/{session_id}/medicines", headers=headers)
    assert meds.status_code == 200
    items = meds.json()
    assert len(items) >= 1
    first = next(item for item in items if item["ai_medicine_name"] == "Pantoprazole")

    # Indication is optional — confirm when drug/strength/dose/frequency are green
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in table["rows"] if r["medicine_id"] == first["id"])
    assert row["fields"]["indication"].get("optional") is True
    # Ensure required cascade fields are selectable if not already green
    for field in ("drug", "route", "strength", "dose", "frequency"):
        cell = row["fields"][field]
        if cell["status"] == "green":
            continue
        if field == "drug":
            value = "Pantoprazole"
        else:
            assert cell["options"], f"{field} options empty"
            value = cell["options"][0]["value"] if isinstance(cell["options"][0], dict) else cell["options"][0]
        assert (
            client.post(
                f"/api/v1/reviews/{session_id}/medicines/{first['id']}/fields",
                headers=headers,
                json={"field": field, "value": value},
            ).status_code
            == 200
        )
        row = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
        row = next(r for r in row["rows"] if r["medicine_id"] == first["id"])

    verify = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{first['id']}/verify",
        headers=headers,
        json={"status": "confirmed"},
    )
    assert verify.status_code == 200
    assert verify.json()["pharmacist_status"] == "confirmed"

    # Legacy verify path must leave HITL audit
    audit = client.get(f"/api/v1/reviews/{session_id}/hitl-audit", headers=headers)
    assert audit.status_code == 200
    events = audit.json().get("events") or audit.json()
    if isinstance(events, dict):
        events = events.get("events") or []
    assert any(
        (e.get("event_type") == "hitl.row_confirmed")
        for e in (events if isinstance(events, list) else [])
    )
