"""HITL field-by-field verification cascade tests."""

from io import BytesIO

from app.services.field_verification import _is_forbidden_placeholder
from app.services.pipeline import PrescriptionPipeline
from app.services.therapeutic.seed_data import indication_options_for_drug


def test_indication_options_deduplicated_from_datasets():
    opts = indication_options_for_drug("Amoxicillin")
    values = [o["value"].lower() for o in opts]
    assert len(values) == len(set(values))
    assert opts, "Expected at least one indication option from seed and/or catalog"
    for opt in opts:
        assert set(opt["sources"]).issubset({"DrugBank", "FDA_SPL", "FDA_NDC"})


def test_forbidden_placeholders():
    assert _is_forbidden_placeholder("Unknown")
    assert _is_forbidden_placeholder("N/A")
    assert _is_forbidden_placeholder("  none  ")
    assert not _is_forbidden_placeholder("Oral")
    assert not _is_forbidden_placeholder("200 mg")


def test_pipeline_emits_misspelled_arcabose():
    result = PrescriptionPipeline().run(b"demo-hitl")
    names = [m.medicine_name for m in result.parsed_medicines]
    assert "Arcabose" in names
    assert "Pantoprazole" in names
    assert "Cetirizine" in names
    assert "Acetaminophen" in names


def _headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pick_first_option(options):
    if not options:
        return None
    first = options[0]
    if isinstance(first, dict):
        return first.get("value") or first.get("canonical_name") or first.get("label")
    return first


def test_verification_table_cascade(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    monkeypatch.setattr("app.services.ocr.engines.settings.ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda *_a, **_k: None,
    )
    headers = _headers(client)
    files = {"file": ("hitl.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    assert client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"}).status_code == 200

    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers)
    assert table.status_code == 200
    rows = table.json()["rows"]
    arcabose = next(r for r in rows if r["fields"]["drug"]["value"] == "Arcabose")
    assert arcabose["fields"]["drug"]["status"] == "red"
    assert arcabose["can_confirm"] is False
    assert arcabose["fields"]["route"]["locked"] is True
    assert arcabose["fields"]["strength"]["locked"] is True
    assert arcabose["fields"]["indication"]["locked"] is True

    # Confirm blocked while red
    blocked = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/confirm-fields",
        headers=headers,
    )
    assert blocked.status_code == 422

    # Unknown rejected on drug
    unknown = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
        headers=headers,
        json={"field": "drug", "value": "Unknown"},
    )
    assert unknown.status_code == 422

    # Fix drug → route unlocks; strength unlocks only after route is catalog-matched
    fixed_drug = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
        headers=headers,
        json={"field": "drug", "value": "acarbose"},
    )
    assert fixed_drug.status_code == 200
    body = fixed_drug.json()
    assert body["fields"]["drug"]["status"] == "green"
    assert body["fields"]["route"]["locked"] is False
    assert "Unknown" not in [str(o) for o in body["fields"]["route"]["options"]]

    if body["fields"]["route"]["status"] != "green":
        assert body["fields"]["strength"]["locked"] is True
        # Strength before route must fail
        early_strength = client.post(
            f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
            headers=headers,
            json={"field": "strength", "value": "50 mg"},
        )
        assert early_strength.status_code == 422
        route_val = _pick_first_option(body["fields"]["route"]["options"])
        assert route_val
        fixed_route = client.post(
            f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
            headers=headers,
            json={"field": "route", "value": route_val},
        )
        assert fixed_route.status_code == 200
        route_body = fixed_route.json()
    else:
        # Single catalog route (e.g. Oral) may auto-match after drug confirm
        route_body = body

    assert route_body["fields"]["route"]["status"] == "green"
    assert route_body["fields"]["strength"]["locked"] is False
    strength_opts = route_body["fields"]["strength"]["options"]
    assert strength_opts
    assert any("50" in str(o) or "25" in str(o) or "100" in str(o) for o in strength_opts)

    strength_val = next(
        (o for o in strength_opts if "50" in str(o)),
        _pick_first_option(strength_opts),
    )
    fixed_strength = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
        headers=headers,
        json={"field": "strength", "value": strength_val},
    )
    assert fixed_strength.status_code == 200
    assert fixed_strength.json()["fields"]["strength"]["status"] == "green"

    # Dose + frequency cascade (may already be green from OCR/catalog auto-match)
    state = fixed_strength.json()
    assert state["fields"]["dose"]["locked"] is False
    if state["fields"]["dose"]["status"] == "red":
        dose_val = _pick_first_option(state["fields"]["dose"]["options"])
        assert dose_val
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
            headers=headers,
            json={"field": "dose", "value": dose_val},
        )
    state = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in state["rows"] if r["medicine_id"] == arcabose["medicine_id"])
    if row["fields"]["frequency"]["status"] == "red":
        assert row["fields"]["indication"]["locked"] is True
        freq_val = _pick_first_option(row["fields"]["frequency"]["options"])
        assert freq_val
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
            headers=headers,
            json={"field": "frequency", "value": freq_val},
        )

    final = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in final["rows"] if r["medicine_id"] == arcabose["medicine_id"])
    # Indication is optional — unlocked only after five required greens; confirm allowed without it
    assert row["fields"]["indication"].get("optional") is True
    assert row["fields"]["indication"]["locked"] is False
    assert row["can_confirm"] is True
    assert row.get("confirm_hint") in (None, "")
    confirmed = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/confirm-fields",
        headers=headers,
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["pharmacist_status"] == "confirmed"
    assert body["fields"]["indication"]["locked"] is False
    assert body["fields"]["route"]["locked"] is True

    # Post-confirm: SIG locked but indication editable for alternatives
    blocked_route = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
        headers=headers,
        json={"field": "route", "value": "Oral"},
    )
    assert blocked_route.status_code == 422

    ind_opts = body["fields"]["indication"]["options"]
    if ind_opts:
        ind_val = _pick_first_option(ind_opts)
        added = client.post(
            f"/api/v1/reviews/{session_id}/medicines/{arcabose['medicine_id']}/fields",
            headers=headers,
            json={"field": "indication", "value": ind_val},
        )
        assert added.status_code == 200
        added_body = added.json()
        assert added_body["pharmacist_status"] == "confirmed"
        assert added_body["fields"]["indication"]["value"] == ind_val
        assert added_body["fields"]["indication"]["locked"] is False


def test_indication_editable_after_confirm(client, monkeypatch):
    """Confirm without indication, then add indication for therapeutic alternatives."""
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    monkeypatch.setattr("app.services.ocr.engines.settings.ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda *_a, **_k: None,
    )
    headers = _headers(client)
    files = {"file": ("hitl.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"})

    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in table["rows"] if r["fields"]["drug"]["value"] == "Arcabose")
    med_id = row["medicine_id"]

    client.post(
        f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
        headers=headers,
        json={"field": "drug", "value": "Acarbose"},
    )
    state = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in state["rows"] if r["medicine_id"] == med_id)

    if row["fields"]["route"]["status"] != "green":
        route_val = _pick_first_option(row["fields"]["route"]["options"])
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
            headers=headers,
            json={"field": "route", "value": route_val},
        )
    state = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in state["rows"] if r["medicine_id"] == med_id)

    if row["fields"]["strength"]["status"] != "green":
        strength_val = _pick_first_option(row["fields"]["strength"]["options"])
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
            headers=headers,
            json={"field": "strength", "value": strength_val},
        )
    state = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in state["rows"] if r["medicine_id"] == med_id)

    if row["fields"]["dose"]["status"] == "red":
        dose_val = _pick_first_option(row["fields"]["dose"]["options"])
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
            headers=headers,
            json={"field": "dose", "value": dose_val},
        )
    state = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in state["rows"] if r["medicine_id"] == med_id)

    if row["fields"]["frequency"]["status"] == "red":
        freq_val = _pick_first_option(row["fields"]["frequency"]["options"])
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
            headers=headers,
            json={"field": "frequency", "value": freq_val},
        )

    confirmed = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{med_id}/confirm-fields",
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["pharmacist_status"] == "confirmed"
    assert not (confirmed.json()["fields"]["indication"]["value"] or "").strip()

    ind_opts = confirmed.json()["fields"]["indication"]["options"]
    assert ind_opts
    ind_val = _pick_first_option(ind_opts)
    post = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{med_id}/fields",
        headers=headers,
        json={"field": "indication", "value": ind_val},
    )
    assert post.status_code == 200
    assert post.json()["pharmacist_status"] == "confirmed"
    assert post.json()["fields"]["indication"]["value"] == ind_val


def test_unable_to_verify_without_confirm(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", True)
    monkeypatch.setattr("app.services.ocr.engines.settings.ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda *_a, **_k: None,
    )
    headers = _headers(client)
    files = {"file": ("hitl.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    assert client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"}).status_code == 200
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    row = next(r for r in table["rows"] if r["fields"]["drug"]["value"] == "Arcabose")
    assert row["can_confirm"] is False
    resolved = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{row['medicine_id']}/verify",
        headers=headers,
        json={"status": "excluded", "reason": "Cannot match first five catalog fields"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["pharmacist_status"] == "excluded"


def test_confirm_blocked_when_mock_ocr_disallowed(client, monkeypatch):
    monkeypatch.setattr("app.services.field_verification.settings.HITL_ALLOW_MOCK_CONFIRM", False)
    monkeypatch.setattr("app.services.ocr.engines.settings.ENABLE_TROCR_RETRY", False)
    monkeypatch.setattr(
        "app.services.ocr.engines.google_vision_document_text",
        lambda *_a, **_k: None,
    )
    headers = _headers(client)
    files = {"file": ("hitl.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"9" * 80), "image/png")}
    session_id = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    assert client.post(f"/api/v1/ocr/{session_id}/run", headers=headers, json={"engine": "pipeline"}).status_code == 200
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    assert table["rows"]
    assert any(r.get("ocr_is_mock") for r in table["rows"])
    row = next(r for r in table["rows"] if r.get("confirm_blocked_mock_ocr"))
    assert row["can_confirm"] is False
    blocked = client.post(
        f"/api/v1/reviews/{session_id}/medicines/{row['medicine_id']}/confirm-fields",
        headers=headers,
    )
    assert blocked.status_code == 422
    assert "MOCK OCR" in str(blocked.json().get("detail", "")).upper()
