"""Phase 2 registration / consent / admin approval tests."""

import uuid

from app.core.research_content import CONSENT_STATEMENTS, PIS_VERSION
from app.security.encryption import decrypt_field, encrypt_field


def _payload(**overrides):
    data = {
        "username": f"pharm_{uuid.uuid4().hex[:10]}",
        "password": "SecurePharm!9xK2ab",
        "confirm_password": "SecurePharm!9xK2ab",
        "pharmacist_registration_id": f"GPhC-{uuid.uuid4().hex[:8]}",
        "age_over_18": True,
        "pis_version": PIS_VERSION,
        "pis_scroll_acknowledged": True,
        "pis_label_accepted": True,
        "consent_form_version": "1.0",
        "accepted_statement_numbers": list(range(1, 19)),
        "electronic_affirmation": True,
    }
    data.update(overrides)
    return data


def test_consent_has_18_statements():
    assert len(CONSENT_STATEMENTS) == 18


def test_field_encryption_roundtrip():
    token = encrypt_field("GPhC-12345")
    assert token != "GPhC-12345"
    assert decrypt_field(token) == "GPhC-12345"


def test_under_18_blocked(client):
    response = client.post(
        "/api/v1/auth/register/complete",
        json=_payload(age_over_18=False, username=f"u18_{uuid.uuid4().hex[:8]}"),
    )
    assert response.status_code == 422


def test_missing_consent_blocked(client):
    response = client.post(
        "/api/v1/auth/register/complete",
        json=_payload(
            username=f"noconsent_{uuid.uuid4().hex[:8]}",
            accepted_statement_numbers=list(range(1, 18)),
        ),
    )
    assert response.status_code == 422


def test_register_pending_then_admin_approve(client):
    payload = _payload()
    username = payload["username"]
    reg = client.post("/api/v1/auth/register/complete", json=payload)
    assert reg.status_code == 200
    assert reg.json()["status"] == "pending_review"

    pending_login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": payload["password"]},
    )
    assert pending_login.status_code == 200
    assert pending_login.json()["user"]["status"] == "pending"

    admin_token = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!234"},
    ).json()["access_token"]

    approve = client.post(
        f"/api/v1/admin/registrations/{reg.json()['id']}/approve",
        json={"confirmed_role": "pharmacist"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200

    active_login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": payload["password"]},
    )
    assert active_login.json()["user"]["status"] == "active"


def test_reviewer_cannot_approve(client):
    login = None
    for candidate in ("ChangeMeReview!234", "ReviewSecure!9xK2", "ReviewSecure!9xK3"):
        probe = client.post(
            "/api/v1/auth/login",
            json={"username": "reviewer", "password": candidate},
        )
        if probe.status_code == 200:
            login = probe
            break
    assert login is not None, "Could not login as reviewer"
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/admin/registrations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_register_rejects_weak_password(client):
    response = client.post(
        "/api/v1/auth/register/complete",
        json=_payload(
            username=f"weak_{uuid.uuid4().hex[:8]}",
            password="password12345",
            confirm_password="password12345",
        ),
    )
    assert response.status_code == 422


def test_pending_pharmacist_blocked_from_clinical(client):
    payload = _payload()
    username = payload["username"]
    password = payload["password"]
    reg = client.post("/api/v1/auth/register/complete", json=payload)
    assert reg.status_code == 200

    pending = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert pending.status_code == 200
    token = pending.json()["access_token"]
    assert pending.json()["user"]["status"] == "pending"

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["status"] == "pending"

    clinical = client.get(
        "/api/v1/catalog/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert clinical.status_code == 403

    upload = client.post(
        "/api/v1/prescriptions/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"x" * 40, "image/png")},
    )
    assert upload.status_code == 403


def test_admin_reject_keeps_account_inactive(client):
    payload = _payload()
    username = payload["username"]
    password = payload["password"]
    reg = client.post("/api/v1/auth/register/complete", json=payload)
    assert reg.status_code == 200
    request_id = reg.json()["id"]

    admin_token = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!234"},
    ).json()["access_token"]

    rejected = client.post(
        f"/api/v1/admin/registrations/{request_id}/reject",
        json={"confirmed_role": "pharmacist", "reason": "Incomplete credentials"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    # Inactive rejected accounts cannot authenticate for clinical use
    assert login.status_code == 401


def test_health_phase_marker(client):
    body = client.get("/health").json()
    assert "phase" in body
