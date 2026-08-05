"""Phase 1b health behaviour (mocked DB) — kept for regression."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok_when_db_ok():
    with patch("app.main.check_database", return_value={"status": "ok", "engine": "postgresql+psycopg"}):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"


def test_health_degraded_when_db_down():
    with patch("app.main.check_database", return_value={"status": "error", "detail": "OperationalError"}):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "error"
