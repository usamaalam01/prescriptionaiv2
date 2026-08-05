"""Milestone 4: therapeutic alternatives + evaluation snapshot tests."""

from io import BytesIO

from app.services.knowledge import lookup_drug
from app.services.alternatives_service import suggest_for_medicine
from app.models.prescription import PrescriptionMedicine


def test_knowledge_lookup_seed_medicines():
    amox = lookup_drug("Amoxicillin")
    assert amox is not None
    assert amox.alternatives
    assert any(c.source == "DrugBank" for c in amox.citations)


def test_suggest_for_medicine_includes_citations():
    med = PrescriptionMedicine(
        id="x",
        session_id="s",
        item_number=1,
        ai_medicine_name="Ibuprofen",
        parser_confidence=0.9,
        formulary_matched=True,
        pharmacist_status="extracted",
    )
    items = suggest_for_medicine(med)
    assert items
    assert items[0]["citations"]
    assert "Decision-support only" in items[0]["explanation"]


def _headers(client, username: str, password: str):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_alternatives_api_and_feedback(client):
    headers = _headers(client, "pharmacist", "ChangeMePharm!234")
    files = {"file": ("synthetic.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"2" * 80), "image/png")}
    upload = client.post("/api/v1/prescriptions/upload", headers=headers, files=files)
    assert upload.status_code == 200
    session_id = upload.json()["id"]

    run = client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"})
    assert run.status_code == 200

    alts = client.get(f"/api/v1/reviews/{session_id}/alternatives", headers=headers)
    assert alts.status_code == 200
    payload = alts.json()
    assert len(payload) >= 3
    assert payload[0]["citations"]
    assert payload[0]["is_mock_knowledge"] is True

    suggestion_id = payload[0]["id"]
    fb = client.post(
        f"/api/v1/reviews/{session_id}/alternatives/{suggestion_id}/feedback",
        headers=headers,
        json={"decision": "noted", "note": "Academic review only"},
    )
    assert fb.status_code == 200
    assert fb.json()["decision"] == "noted"


def test_reviewer_evaluation_snapshot(client):
    headers = _headers(client, "reviewer", "ChangeMeReview!234")
    response = client.get("/api/v1/research/evaluation-snapshot", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "5-therapeutic"
    assert "disclaimer" in body
    assert "sessions_total" in body


def test_pharmacist_cannot_access_evaluation_snapshot(client):
    headers = _headers(client, "pharmacist", "ChangeMePharm!234")
    response = client.get("/api/v1/research/evaluation-snapshot", headers=headers)
    assert response.status_code == 403


def test_health_phase_4(client):
    assert client.get("/health").json()["phase"] == "5-therapeutic"
