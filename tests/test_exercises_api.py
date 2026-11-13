"""Integration tests for the ``/exercises`` endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.types import ParsedSession, SessionMetadata
from athlete_stress_sim.core.storage.session_store import SessionStore

_START = datetime(2026, 10, 3, 7, 0, 0)


def _session(sport: str, sub_sport: str, duration_s: float) -> ParsedSession:
    return ParsedSession(
        metadata=SessionMetadata(
            sport=sport,
            sub_sport=sub_sport,
            start_time=_START,
            duration_s=duration_s,
        ),
        samples=[],
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("run1", _session("running", "street", 1800.0), "data/raw/run1.fit")
    store.save_session(
        "gym1", _session("training", "strength_training", 3600.0), "data/raw/gym1.fit"
    )
    store.save_session(
        "elli1", _session("fitness_equipment", "elliptical", 2400.0), "data/raw/elli1.fit"
    )
    app.dependency_overrides[get_session_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_all_exercises(client: TestClient) -> None:
    response = client.get("/exercises")

    assert response.status_code == 200
    assert {item["exercise_id"] for item in response.json()} == {"run1", "gym1", "elli1"}


def test_list_only_gym_exercises(client: TestClient) -> None:
    response = client.get("/exercises", params={"kind": "gym"})

    assert response.status_code == 200
    assert {item["exercise_id"] for item in response.json()} == {"gym1"}


def test_list_only_running_exercises(client: TestClient) -> None:
    response = client.get("/exercises", params={"kind": "run"})

    assert response.status_code == 200
    assert {item["exercise_id"] for item in response.json()} == {"run1"}


def test_list_only_elliptical_exercises(client: TestClient) -> None:
    response = client.get("/exercises", params={"kind": "elliptical"})

    assert response.status_code == 200
    assert {item["exercise_id"] for item in response.json()} == {"elli1"}


def test_elliptical_is_not_listed_as_running(client: TestClient) -> None:
    response = client.get("/exercises", params={"kind": "run"})

    assert "elli1" not in {item["exercise_id"] for item in response.json()}


def test_get_exercise(client: TestClient) -> None:
    response = client.get("/exercises/run1")

    assert response.status_code == 200
    assert response.json()["sport"] == "running"


def test_get_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.get("/exercises/missing").status_code == 404


def test_set_rpe_computes_load(client: TestClient) -> None:
    response = client.post("/exercises/gym1/rpe", json={"rpe": 6})

    assert response.status_code == 200
    body = response.json()
    assert body["rpe"] == 6
    assert body["load"] == pytest.approx(360.0)  # 6 * 60 min


def test_set_rpe_out_of_range_is_rejected(client: TestClient) -> None:
    assert client.post("/exercises/gym1/rpe", json={"rpe": 11}).status_code == 422


def test_set_rpe_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.post("/exercises/missing/rpe", json={"rpe": 5}).status_code == 404


def test_update_exercise_metadata(client: TestClient) -> None:
    response = client.patch(
        "/exercises/run1",
        json={"distance_m": 10_000.0, "duration_s": 3000.0, "avg_hr": 150},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["distance_m"] == pytest.approx(10_000.0)
    assert body["duration_s"] == pytest.approx(3000.0)
    assert body["avg_hr"] == 150


def test_update_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.patch("/exercises/missing", json={"distance_m": 1000.0}).status_code == 404


def test_update_exercise_rejects_negative_distance(client: TestClient) -> None:
    assert client.patch("/exercises/run1", json={"distance_m": -1.0}).status_code == 422
