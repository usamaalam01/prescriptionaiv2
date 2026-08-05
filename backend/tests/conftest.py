"""Shared test client. Auth tests expect Postgres running and `python -m app.db.seed`."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

# Reload settings from .env after process start
get_settings.cache_clear()


@pytest.fixture()
def client(monkeypatch):
    # Integration HITL flows still need dose/freq options when SPL SIG index is sparse.
    monkeypatch.setattr(
        "app.core.config.settings.HITL_ALLOW_DOSE_TEMPLATES",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.config.settings.HITL_ALLOW_FREQ_TEMPLATES",
        True,
        raising=False,
    )
    with TestClient(app) as test_client:
        yield test_client
