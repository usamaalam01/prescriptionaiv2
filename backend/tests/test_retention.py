"""Retention policy helpers (no DB required for policy shape)."""

from app.services.retention import retention_policy


def test_retention_policy_shape():
    policy = retention_policy()
    assert policy["retention_hours"] >= 1
    assert "delete_on_cancel" in policy
    assert "delete_when_session_confirmed" in policy
    assert "note" in policy
