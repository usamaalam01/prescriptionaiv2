"""Live smoke test against running PharmaAssist servers."""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=60.0)

    print("1) health")
    h = client.get("/health")
    print(h.status_code, h.json())
    assert h.status_code == 200 and h.json()["phase"] == "5-therapeutic"

    print("2) login pharmacist")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    )
    print(login.status_code)
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("3) upload + pipeline")
    files = {"file": ("smoke.png", b"\x89PNG\r\n\x1a\n" + b"7" * 80, "image/png")}
    up = client.post("/api/v1/prescriptions/upload", headers=headers, files=files)
    print("upload", up.status_code, up.json().get("id"))
    assert up.status_code == 200
    session_id = up.json()["id"]
    run = client.post(
        f"/api/v1/ocr/{session_id}/run",
        headers=headers,
        json={"engine": "pipeline"},
    )
    print(
        "ocr",
        run.status_code,
        "mock=",
        run.json().get("is_mock"),
        "conf=",
        run.json().get("confidence"),
    )
    assert run.status_code == 200

    print("4) HITL confirm medicine rows")
    table = client.get(f"/api/v1/reviews/{session_id}/verification-table", headers=headers)
    assert table.status_code == 200
    rows = table.json()["rows"]
    print(
        "rows",
        [
            (r["fields"]["drug"]["value"], r["can_confirm"], r["pharmacist_status"])
            for r in rows
        ],
    )

    confirmed_ids: list[str] = []
    for row in rows:
        mid = row["medicine_id"]
        drug = row["fields"]["drug"]["value"]
        if drug == "Ibrufen":
            r = client.post(
                f"/api/v1/reviews/{session_id}/medicines/{mid}/fields",
                headers=headers,
                json={"field": "drug", "value": "Ibuprofen"},
            )
            assert r.status_code == 200, r.text
            row = r.json()

        for field in ("drug", "strength", "dose", "frequency", "indication"):
            f = row["fields"][field]
            if f.get("status") == "red":
                opts = f.get("options") or []
                if not opts:
                    print("No options for", field, "on", drug)
                    return 1
                first = opts[0]
                value = first["value"] if isinstance(first, dict) else first
                r = client.post(
                    f"/api/v1/reviews/{session_id}/medicines/{mid}/fields",
                    headers=headers,
                    json={"field": field, "value": value},
                )
                assert r.status_code == 200, r.text
                row = r.json()

        table = client.get(
            f"/api/v1/reviews/{session_id}/verification-table", headers=headers
        ).json()
        row = next(x for x in table["rows"] if x["medicine_id"] == mid)
        if not row["can_confirm"]:
            print("cannot confirm", row["fields"])
            return 1
        conf = client.post(
            f"/api/v1/reviews/{session_id}/medicines/{mid}/confirm-fields",
            headers=headers,
        )
        print(
            "confirm",
            row["fields"]["drug"]["value"],
            conf.status_code,
            conf.json().get("pharmacist_status"),
        )
        assert conf.status_code == 200
        confirmed_ids.append(mid)

    print("5) evaluate therapeutic alternatives (per-medicine indications)")
    table = client.get(
        f"/api/v1/reviews/{session_id}/verification-table", headers=headers
    ).json()
    payload_meds = []
    for row in table["rows"]:
        if row["pharmacist_status"] != "confirmed":
            continue
        name = row["fields"]["drug"]["value"]
        indication = "bacterial infection"
        if "Ibuprofen" in name or "Paracetamol" in name or "Naproxen" in name:
            indication = "pain"
        if "Salbutamol" in name or "Albuterol" in name:
            indication = "asthma"
        payload_meds.append(
            {
                "prescription_item_id": row["medicine_id"],
                "medicine_name": name,
                "pharmacist_verified": True,
                "verified_indication": indication,
                "identity_confirmed_by_pharmacist": True,
            }
        )

    ev = client.post(
        "/api/v1/therapeutic-alternatives/evaluate",
        headers=headers,
        json={
            "prescription_id": session_id,
            "use_confirmed_session_medicines": True,
            "top_n": 5,
            "patient_context": {"allergy_status": "none_known", "allergies": []},
            "prescribed_medicines": payload_meds,
        },
    )
    print("evaluate", ev.status_code)
    assert ev.status_code == 200, ev.text
    body = ev.json()
    print("evaluation_id", body["evaluation_id"], "demo", body.get("demo_label"))
    for med in body["medicine_results"]:
        print(
            "-",
            med["source_medicine"]["medicine_name"],
            med["evaluation_status"],
            "eligible=",
            [c["candidate_name"] for c in med.get("eligible_alternatives") or []],
            "blocked=",
            len(med.get("blocked_candidates") or []),
            "withdrawn=",
            len(med.get("withdrawn_candidates") or []),
        )
        for c in med.get("eligible_alternatives") or []:
            print(
                "   #",
                c.get("rank"),
                c["candidate_name"],
                "score",
                c["evidence_match_score"],
                c["status"],
            )

    eid = body["evaluation_id"]
    got = client.get(f"/api/v1/therapeutic-alternatives/{eid}", headers=headers)
    print("6) get evaluation", got.status_code)
    assert got.status_code == 200

    src = client.get(f"/api/v1/therapeutic-alternatives/{eid}/sources", headers=headers)
    print("7) sources", src.status_code, "claims=", len(src.json().get("source_claims") or []))
    assert src.status_code == 200
    assert src.json().get("demo_label") == "DEMO DATA"

    decision_ok = False
    for med in body["medicine_results"]:
        alts = med.get("eligible_alternatives") or []
        if not alts:
            continue
        cand = alts[0]
        dec = client.post(
            f"/api/v1/therapeutic-alternatives/{eid}/decision",
            headers=headers,
            json={
                "prescription_item_id": med["prescription_item_id"],
                "candidate_drug_id": cand["candidate_drug_id"],
                "candidate_name": cand["candidate_name"],
                "action": "accept_for_review",
                "reason": "Smoke test: accept for further pharmacist review only",
                "note": "Automated prototype smoke test",
            },
        )
        print("8) decision", dec.status_code, dec.json())
        assert dec.status_code == 200
        decision_ok = True
        break
    assert decision_ok, "No eligible alternative to decide on"

    # Frontend reachable
    fe = httpx.get("http://127.0.0.1:5173/", timeout=10.0)
    print("9) frontend", fe.status_code)
    assert fe.status_code == 200

    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("SMOKE FAILED:", exc, file=sys.stderr)
        raise
