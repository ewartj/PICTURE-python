"""
Integration tests for analytics API routes.

Uses httpx AsyncClient against the FastAPI app (no real data files needed —
the data_dir dependency is overridden with test fixtures).
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_rdvs

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------


def _make_test_rdvs() -> dict[str, pd.DataFrame]:
    pde = pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003"],
            "birth_date": pd.to_datetime(["1980-01-01", "1990-01-01", "1975-01-01"]),
            "sex_name": ["Female", "Male", "Female"],
            "death_date": [None, None, None],
            "cohort": ["All", "All", "All"],
        }
    )
    dia = pd.DataFrame(
        {
            "project_id": ["P001", "P001", "P002", "P003"],
            "diag_name": ["Asthma", "Diabetes", "Asthma", "Hypertension"],
            "start_datetime": pd.to_datetime(["2020-01-01"] * 4),
            "end_datetime": pd.to_datetime(["2020-06-01"] * 4),
            "cohort_id": ["P001-000001", "P001-000001", "P002-000001", "P003-000001"],
            "cohort": ["All", "All", "All", "All"],
        }
    )
    return {"pde": pde, "dia": dia}


# ---------------------------------------------------------------------------
# Client with dependency override
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app.dependency_overrides[get_rdvs] = lambda: _make_test_rdvs()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_frequency_returns_200(client):
    r = client.post(
        "/analytics/frequency",
        json={
            "data_dir": "/fake",
            "rdv": "dia",
            "event_col": "diag_name",
            "cohort_definitions": [],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "table" in body
    assert "plot" in body
    assert "meta" in body


def test_frequency_correct_event_count(client):
    r = client.post(
        "/analytics/frequency",
        json={
            "data_dir": "/fake",
            "rdv": "dia",
            "event_col": "diag_name",
            "cohort_definitions": [],
        },
    )
    table = {row["event"]: row for row in r.json()["table"]}
    assert table["Asthma"]["All.count"] == 2  # P001 and P002


def test_frequency_unknown_rdv_returns_404(client):
    r = client.post(
        "/analytics/frequency",
        json={
            "data_dir": "/fake",
            "rdv": "nonexistent",
            "event_col": "diag_name",
        },
    )
    assert r.status_code == 404
