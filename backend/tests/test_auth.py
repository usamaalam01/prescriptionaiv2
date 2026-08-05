"""Phase 1c authentication and RBAC tests (requires Postgres + seed)."""

from app.security.passwords import hash_password, verify_password


def test_argon2id_hash_and_verify():
    digest = hash_password("ChangeMeAdmin!234")
    assert digest.startswith("$argon2id$")
    assert verify_password("ChangeMeAdmin!234", digest)
    assert not verify_password("wrong-password", digest)


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["role"] == "administrator"
    assert "password" not in body["user"]


def test_login_invalid_is_generic(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "not-the-right-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_token(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    )
    token = login.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "pharmacist"
    assert response.json()["role"] == "pharmacist"


def test_rbac_admin_only(client):
    admin = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!234"},
    ).json()["access_token"]
    pharmacist = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    ).json()["access_token"]

    ok = client.get("/api/v1/rbac/administrator", headers={"Authorization": f"Bearer {admin}"})
    denied = client.get(
        "/api/v1/rbac/administrator",
        headers={"Authorization": f"Bearer {pharmacist}"},
    )
    assert ok.status_code == 200
    assert denied.status_code == 403


def test_health_phase_reports(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "award-path"
    assert "catalog" in body
    assert "components" in body
    assert "database" in body


def test_ready_endpoint(client):
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    assert "status" in response.json()


def test_forgot_password_flow(client):
    unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "definitely-not-a-real-user-xyz"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["temporary_password"] is None

    reset = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "pharmacist"},
    )
    assert reset.status_code == 200
    temporary = reset.json()["temporary_password"]
    assert temporary and temporary.startswith("Tmp!")

    old = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "ChangeMePharm!234"},
    )
    assert old.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": temporary},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["must_change_password"] is True
    assert body["user"]["status"] == "password_reset_required"

    restored = "ChangeMePharm!234"
    change = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {body['access_token']}"},
        json={"current_password": temporary, "new_password": restored},
    )
    assert change.status_code == 200
    assert change.json()["must_change_password"] is False
    assert change.json()["status"] == "active"

    again = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": restored},
    )
    assert again.status_code == 200
    assert again.json()["user"]["must_change_password"] is False


def test_change_password_flow(client):
    current = None
    token = None
    for candidate in ("ChangeMeReview!234", "ReviewSecure!9xK2", "ReviewSecure!9xK3"):
        probe = client.post(
            "/api/v1/auth/login",
            json={"username": "reviewer", "password": candidate},
        )
        if probe.status_code == 200:
            token = probe.json()["access_token"]
            current = candidate
            break
    assert token and current, "Could not login as reviewer with known passwords"

    weak = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": current, "new_password": "short"},
    )
    assert weak.status_code == 422

    target = "ReviewSecure!9xK3" if current != "ReviewSecure!9xK3" else "ReviewSecure!9xK2"
    ok = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": current, "new_password": target},
    )
    assert ok.status_code == 200
    assert ok.json()["must_change_password"] is False

    old = client.post(
        "/api/v1/auth/login",
        json={"username": "reviewer", "password": current},
    )
    assert old.status_code == 401
    again = client.post(
        "/api/v1/auth/login",
        json={"username": "reviewer", "password": target},
    )
    assert again.status_code == 200
