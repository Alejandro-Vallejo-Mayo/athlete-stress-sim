"""Integration tests for the race prediction endpoints (``RF-05.4``)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.types import ParsedSession, Sample, SessionMetadata
from athlete_stress_sim.core.metrics.race_prediction import riegel_time
from athlete_stress_sim.core.storage.session_store import SessionStore

_START = datetime(2026, 10, 1, 7, 0, 0)


def _race_hr() -> int:
    return round(physiology.hr_rest + 0.9 * (physiology.hr_max - physiology.hr_rest))


def _run_session(start: datetime, distance_m: float, duration_s: float) -> ParsedSession:
    speed = distance_m / duration_s
    hr = _race_hr()
    samples = [
        Sample(
            timestamp=start + timedelta(seconds=elapsed),
            elapsed_s=float(elapsed),
            hr=hr,
            speed_mps=speed,
            distance_m=distance_m * elapsed / duration_s,
            is_valid=True,
        )
        for elapsed in range(0, int(duration_s) + 1, 5)
    ]
    return ParsedSession(
        metadata=SessionMetadata(
            sport="running",
            sub_sport="street",
            start_time=start,
            duration_s=duration_s,
            distance_m=distance_m,
        ),
        samples=samples,
    )


def _seeded_store(path: Path) -> SessionStore:
    store = SessionStore(path)
    descriptions = [
        (_START, 3000.0, 900.0),
        (_START + timedelta(days=2), 5000.0, 1600.0),
        (_START + timedelta(days=4), 10000.0, 3400.0),
    ]
    for index, (start, distance_m, duration_s) in enumerate(descriptions):
        exercise_id = f"run{index}"
        store.save_session(
            exercise_id,
            _run_session(start, distance_m, duration_s),
            f"data/raw/{exercise_id}.fit",
        )
    return store


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = _seeded_store(tmp_path / "prediction.duckdb")
    app.dependency_overrides[get_session_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_best_efforts_detects_quality_efforts(client: TestClient) -> None:
    response = client.get("/metrics/best-efforts")

    assert response.status_code == 200
    body = response.json()
    distances = {effort["distance_km"] for effort in body}
    assert {3.0, 5.0, 10.0} <= distances
    assert all(effort["tier"] == "race" for effort in body)


def test_race_prediction_uses_detected_efforts(client: TestClient) -> None:
    response = client.post(
        "/metrics/race-prediction",
        json={"distance_km": 21.0975, "model": "auto"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "critical_speed"
    assert body["predicted_time_s"] is not None
    assert body["predicted_time_s"] > 0.0
    assert body["fast_time_s"] <= body["predicted_time_s"] <= body["slow_time_s"]
    assert body["efforts"]


def test_race_prediction_uses_manual_reference(client: TestClient) -> None:
    reference_time = 3300.0
    response = client.post(
        "/metrics/race-prediction",
        json={
            "distance_km": 21.0975,
            "model": "riegel",
            "reference": {"distance_km": 10.0, "time_s": reference_time},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "riegel"
    assert body["confidence"] == "high"
    assert body["predicted_time_s"] == pytest.approx(
        riegel_time(10.0, reference_time, 21.0975, 1.06)
    )
    assert any("manual" in note for note in body["notes"])


def test_race_prediction_without_efforts_returns_none(client: TestClient) -> None:
    response = client.post(
        "/metrics/race-prediction",
        json={"distance_km": 10.0, "use_detected_efforts": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "none"
    assert body["confidence"] == "none"
    assert body["predicted_time_s"] is None


def test_race_prediction_rejects_invalid_distance(client: TestClient) -> None:
    response = client.post(
        "/metrics/race-prediction",
        json={"distance_km": 0.0},
    )

    assert response.status_code == 422
