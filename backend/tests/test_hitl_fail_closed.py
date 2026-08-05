"""Fail-closed catalog option behaviour for evidence-only HITL."""

from app.services.catalog_sig_options import routes_for_drug, strengths_for_route


def test_routes_fail_closed_when_empty():
    assert routes_for_drug([]) == []
    assert routes_for_drug(None, forms=[]) == []
    # Forms may still infer a route (catalog-backed dosage form)
    assert "Oral" in routes_for_drug([], forms=["TABLET"])
    # No invented Oral when nothing is known
    assert routes_for_drug(["not applicable", "n/a"]) == []


def test_strengths_fail_closed_when_route_filter_empties():
    # Inhalation route should not dump oral tablet strengths
    strengths = ["200 mg", "400 mg", "500 mg"]
    assert strengths_for_route(strengths, "Inhalation") == []
    # Oral solids still pass
    out = strengths_for_route(strengths, "Oral")
    assert "200 mg" in out
    assert "400 mg" in out


def test_dose_fail_closed_without_spl_evidence():
    from app.services.catalog_sig_options import build_cascade_options

    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=["ORAL"],
        catalog_strengths=["200 mg"],
        matched_route="Oral",
        matched_strength="200 mg",
        canonical_name="__missing__",
        allow_dose_templates=False,
    )
    assert cascade["dose"]["options"] == []
    assert cascade["dose"]["option_source"] == "FDA_SPL_none"


def test_confirm_disclaimer_on_verification_table(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    monkeypatch.setattr("app.services.ocr.engines.settings.ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda *_a, **_k: None,
    )
    from io import BytesIO

    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("hitl.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    assert client.post(
        f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"}
    ).status_code == 200
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers)
    assert table.status_code == 200
    row = table.json()["rows"][0]
    assert row.get("validation_scope") == "prescription_drug_identity"
    disclaimer = row.get("confirm_disclaimer") or ""
    assert "not a patient clinical record" in disclaimer.lower()
    assert "allergy" in disclaimer.lower()
    assert "indication" in disclaimer.lower()
