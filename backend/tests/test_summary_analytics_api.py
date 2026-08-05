"""Integration tests for Summary Analytics API."""

from io import BytesIO


def _headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _confirm_all(client, headers, session_id):
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers).json()
    for row in table["rows"]:
        mid = row["medicine_id"]
        if row["fields"]["drug"]["value"] == "Arcabose":
            client.post(
                f"/api/v1/reviews/{session_id}/medicines/{mid}/fields",
                headers=headers,
                json={"field": "drug", "value": "Acarbose"},
            )
            row = client.get(
                f"/api/v1/reviews/{session_id}/verification-table", headers=headers
            ).json()["rows"]
            row = next(r for r in row if r["medicine_id"] == mid)
        for field in ("drug", "route", "strength", "dose", "frequency", "indication"):
            f = row["fields"][field]
            if f["status"] == "red":
                # Indication is optional — skip if no options
                if field == "indication" and not f.get("options"):
                    continue
                if not f["options"]:
                    continue
                opt = f["options"][0]
                value = opt["value"] if isinstance(opt, dict) else opt
                row = client.post(
                    f"/api/v1/reviews/{session_id}/medicines/{mid}/fields",
                    headers=headers,
                    json={"field": field, "value": value},
                ).json()
        # Refresh before confirm (cascade may need sequential unlocks)
        row = client.get(
            f"/api/v1/reviews/{session_id}/verification-table", headers=headers
        ).json()["rows"]
        row = next(r for r in row if r["medicine_id"] == mid)
        for field in ("route", "strength", "dose", "frequency"):
            f = row["fields"][field]
            if f["status"] == "red" and f.get("options"):
                opt = f["options"][0]
                value = opt["value"] if isinstance(opt, dict) else opt
                row = client.post(
                    f"/api/v1/reviews/{session_id}/medicines/{mid}/fields",
                    headers=headers,
                    json={"field": field, "value": value},
                ).json()
        client.post(
            f"/api/v1/reviews/{session_id}/medicines/{mid}/confirm-fields",
            headers=headers,
        )


def test_analytics_empty_before_confirm(client):
    headers = _headers(client)
    files = {"file": ("a.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"a" * 40), "image/png")}
    sid = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    client.post(f"/api/v1/ocr/{sid}/run", headers=headers, json={"engine": "pipeline"})
    resp = client.get(f"/api/v1/prescriptions/{sid}/analytics", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "Analytics will appear" in body["message"]


def test_analytics_kpis_and_no_pii(client):
    headers = _headers(client)
    files = {"file": ("b.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"b" * 40), "image/png")}
    sid = client.post("/api/v1/prescriptions/upload", headers=headers, files=files).json()["id"]
    client.post(f"/api/v1/ocr/{sid}/run", headers=headers, json={"engine": "pipeline"})
    _confirm_all(client, headers, sid)

    # Evaluate alternatives so TA metrics populate
    table = client.get(f"/api/v1/reviews/{sid}/verification-table", headers=headers).json()
    meds = [
        {
            "prescription_item_id": r["medicine_id"],
            "medicine_name": r["fields"]["drug"]["value"],
            "pharmacist_verified": True,
            "verified_indication": r["fields"]["indication"]["value"],
            "identity_confirmed_by_pharmacist": True,
        }
        for r in table["rows"]
        if r["pharmacist_status"] == "confirmed"
    ]
    client.post(
        "/api/v1/therapeutic-alternatives/evaluate",
        headers=headers,
        json={
            "prescription_id": sid,
            "use_confirmed_session_medicines": True,
            "patient_context": {"allergy_status": "none_known", "allergies": []},
            "prescribed_medicines": meds,
        },
    )

    resp = client.get(f"/api/v1/prescriptions/{sid}/analytics", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["demo_label"] == "DEMO DATA"
    summary = body["summary"]
    assert summary["prescription_items_detected"] == 3
    assert summary["medicines_confirmed"] == 3
    assert summary["fields_corrected"] >= 2
    assert summary["alternative_evaluations_completed"] == 3
    # Before Accept/Reject, pharmacist TA decision counts are zero
    assert summary["pharmacist_accepted_alternatives"] == 0
    assert summary["pharmacist_rejected_alternatives"] == 0
    assert summary["alternative_accepted"] == 0
    assert summary["alternative_rejected"] == 0
    # Engine eligible/excluded are candidate counts (may be > 0 after evaluate)
    assert summary["eligible_alternatives"] >= 0
    assert summary["excluded_alternatives"] >= 0
    assert "patient_name" not in body

    # CER/WER present for final pipeline
    assert body["text_metrics"]["full_prescription"]["final_cer"] is not None
    assert body["entity_aggregates"]["micro_average_f1"] is not None or body["entity_metrics"]

    # BERTScore is optional; when enabled + packaged, status becomes "calculated"
    assert "bertscore_status" in body
    assert body["bertscore_status"] is not None

    export = client.get(
        f"/api/v1/prescriptions/{sid}/analytics/export",
        headers=headers,
        params={"format": "json", "table": "field_comparison"},
    )
    assert export.status_code == 200
