"""Unit tests for HITL audit helpers (no DB required for payload shape)."""

from app.services.hitl_audit import record_hitl_event


def test_record_hitl_event_builds_row(monkeypatch):
    added = []

    class FakeSession:
        def add(self, obj):
            added.append(obj)

        def flush(self):
            return None

    db = FakeSession()
    row = record_hitl_event(
        db,  # type: ignore[arg-type]
        session_id="sess-1",
        pharmacist_user_id="user-1",
        medicine_id="med-1",
        event_type="hitl.field_corrected",
        field_name="drug",
        payload={"previous": "Ibrufen", "new_value": "Ibuprofen"},
        commit=False,
    )
    assert len(added) == 1
    assert row.event_type == "hitl.field_corrected"
    assert row.field_name == "drug"
    assert "Ibuprofen" in row.payload_json
