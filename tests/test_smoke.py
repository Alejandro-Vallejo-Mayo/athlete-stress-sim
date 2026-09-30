"""Smoke test: validate that the scaffolding imports and responds."""

from __future__ import annotations

from fastapi.testclient import TestClient

from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.main import app

client = TestClient(app)


def test_health_endpoint_reports_ok() -> None:
    """The health endpoint returns an OK status payload."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_physiology_priors_are_consistent() -> None:
    """The default physiological priors are internally consistent."""
    assert physiology.hr_max > physiology.hr_rest
    assert physiology.tau_1 > physiology.tau_2
