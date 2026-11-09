"""Reviewer read-only session review (list, detail, image, medicines) — RBAC + content checks."""

import io
import uuid

import pytest

from app.core.enums import UserStatus
from app.db.session import SessionLocal
from app.models.auth import User
from app.security.passwords import hash_password

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)

TEST_PASSWORD = "test-reviewer-pw-only"


@pytest.fixture()
def reviewer_user():
    """A throwaway reviewer account, independent of any pre-existing local dev-seed state."""
    db = SessionLocal()
    user = User(
        username=f"test-reviewer-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password(TEST_PASSWORD),
        role="reviewer",
        status=UserStatus.ACTIVE.value,
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    username = user.username
    user_id = user.id
    db.close()
    yield username
    db = SessionLocal()
    from app.models.auth import LoginHistory, RefreshToken

    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.query(LoginHistory).filter(LoginHistory.user_id == user_id).delete()
    row = db.get(User, user_id)
    if row:
        db.delete(row)
    db.commit()
    db.close()


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_reviewer_can_list_view_and_cannot_edit(client, reviewer_user):
    pharmacist_token = _login(client, "pharmacist", "ChangeMePharm!234")
    reviewer_token = _login(client, reviewer_user, TEST_PASSWORD)

    upload = client.post(
        "/api/v1/prescriptions/upload",
        headers=_auth(pharmacist_token),
        files={"file": ("rx.png", io.BytesIO(PNG_1X1), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    session_id = upload.json()["id"]

    # Reviewer cannot touch pharmacist-only endpoints for this session.
    pharmacist_only = client.get(
        f"/api/v1/prescriptions/{session_id}", headers=_auth(reviewer_token)
    )
    assert pharmacist_only.status_code == 403

    # Reviewer list endpoint works (seed/dev "pharmacist" user is deliberately excluded
    # from the list by the same real-session filter the Admin Portal uses).
    listing = client.get("/api/v1/reviewer/prescriptions", headers=_auth(reviewer_token))
    assert listing.status_code == 200, listing.text
    assert "disclaimer" in listing.json()

    # Reviewer detail works and reports the owning pharmacist.
    detail = client.get(f"/api/v1/reviewer/prescriptions/{session_id}", headers=_auth(reviewer_token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == session_id
    assert body["pharmacist_username"] == "pharmacist"
    assert body["original_filename"] == "rx.png"

    # Reviewer can fetch the stored image bytes back unchanged.
    image = client.get(f"/api/v1/reviewer/prescriptions/{session_id}/image", headers=_auth(reviewer_token))
    assert image.status_code == 200
    assert image.content == PNG_1X1

    # Reviewer can see the medicines list (empty before OCR, but endpoint must work).
    meds = client.get(f"/api/v1/reviewer/prescriptions/{session_id}/medicines", headers=_auth(reviewer_token))
    assert meds.status_code == 200, meds.text
    assert isinstance(meds.json(), list)

    # Pharmacist cannot use the reviewer-only endpoints (role gate, not ownership).
    denied = client.get("/api/v1/reviewer/prescriptions", headers=_auth(pharmacist_token))
    assert denied.status_code == 403

    # Unauthenticated access is rejected on both list and detail.
    assert client.get("/api/v1/reviewer/prescriptions").status_code == 401
    assert client.get(f"/api/v1/reviewer/prescriptions/{session_id}").status_code == 401


def test_reviewer_detail_404_for_unknown_session(client, reviewer_user):
    reviewer_token = _login(client, reviewer_user, TEST_PASSWORD)
    resp = client.get(
        "/api/v1/reviewer/prescriptions/does-not-exist", headers=_auth(reviewer_token)
    )
    assert resp.status_code == 404


def test_reviewer_router_has_no_write_endpoints(client, reviewer_user):
    reviewer_token = _login(client, reviewer_user, TEST_PASSWORD)
    from app.main import app

    reviewer_paths = {r.path for r in app.routes if getattr(r, "path", "").startswith("/api/v1/reviewer")}
    assert reviewer_paths == {
        "/api/v1/reviewer/prescriptions",
        "/api/v1/reviewer/prescriptions/{session_id}",
        "/api/v1/reviewer/prescriptions/{session_id}/image",
        "/api/v1/reviewer/prescriptions/{session_id}/medicines",
    }
    for r in app.routes:
        if getattr(r, "path", "").startswith("/api/v1/reviewer"):
            assert r.methods == {"GET"}, f"{r.path} exposes non-GET methods: {r.methods}"
