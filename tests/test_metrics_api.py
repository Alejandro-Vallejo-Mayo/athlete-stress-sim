"""Integration tests for the ``/metrics`` and ``/simulate`` endpoints."""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.types import ParsedSession, Sample, SessionMetadata
from athlete_stress_sim.core.metrics.trimp import trimp_coefficients
from athlete_stress_sim.core.storage.session_store import SessionStore

_RUN_START = datetime(2026, 10, 3, 7, 0, 0)
_RUN_SECONDS = 60
_RUN_HR = 150
_GYM_START = datetime(2026, 10, 4, 18, 0, 0)
_GYM_RPE = 6.0
_GYM_DURATION_S = 3600.0


def _run_session() -> ParsedSession:
    samples = [
        Sample(
            timestamp=_RUN_START + timedelta(seconds=i),
            elapsed_s=float(i),
            hr=_RUN_HR,
            is_valid=True,
        )
        for i in range(_RUN_SECONDS)
    ]
    return ParsedSession(
        metadata=SessionMetadata(
            sport="running",
            sub_sport="street",
            start_time=_RUN_START,
            duration_s=float(_RUN_SECONDS),
        ),
        samples=samples,
    )


def _gym_session() -> ParsedSession:
    return ParsedSession(
        metadata=SessionMetadata(
            sport="training",
            sub_sport="strength_training",
            start_time=_GYM_START,
            duration_s=_GYM_DURATION_S,
        ),
        samples=[],
    )


def _seeded_store(path: Path) -> SessionStore:
    store = SessionStore(path)
    store.save_session("run1", _run_session(), "data/raw/run1.fit")
    store.save_session("gym1", _gym_session(), "data/raw/gym1.fit")
    store.set_rpe("gym1", _GYM_RPE)
    return store


def _client_for(store: SessionStore) -> TestClient:
    app.dependency_overrides[get_session_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = _seeded_store(tmp_path / "sessions.duckdb")
    app.dependency_overrides[get_session_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _expected_run_trimp() -> float:
    """Compute the expected TRIMP independently of the API path."""
    a, b = trimp_coefficients(physiology.sex)
    ratio = (_RUN_HR - physiology.hr_rest) / (physiology.hr_max - physiology.hr_rest)
    per_minute = ratio * a * math.exp(b * ratio)
    return (_RUN_SECONDS / 60.0) * per_minute


def test_trimp_returns_endurance_load(client: TestClient) -> None:
    response = client.get("/metrics/trimp/run1")

    assert response.status_code == 200
    body = response.json()
    assert body["exercise_id"] == "run1"
    assert body["load"] == pytest.approx(_expected_run_trimp())


def test_trimp_returns_strength_load(client: TestClient) -> None:
    response = client.get("/metrics/trimp/gym1")

    assert response.status_code == 200
    assert response.json()["load"] == pytest.approx(_GYM_RPE * (_GYM_DURATION_S / 60.0))


def test_trimp_without_samples_is_null(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("run0", _run_session(), "data/raw/run0.fit")
    store.save_session(
        "empty",
        ParsedSession(
            metadata=SessionMetadata(
                sport="running",
                sub_sport="street",
                start_time=_RUN_START,
                duration_s=float(_RUN_SECONDS),
            ),
            samples=[],
        ),
        "data/raw/empty.fit",
    )
    client = _client_for(store)
    try:
        response = client.get("/metrics/trimp/empty")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["load"] is None


def test_trimp_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.get("/metrics/trimp/missing").status_code == 404


def test_acwr_series_has_contiguous_days(client: TestClient) -> None:
    response = client.get("/metrics/acwr")

    assert response.status_code == 200
    points = response.json()["points"]
    assert [point["date"] for point in points] == ["2026-10-03", "2026-10-04"]
    assert points[0]["acwr"] == pytest.approx(1.0)
    assert points[0]["acute"] == pytest.approx(points[0]["chronic"])
    assert all(point["zone"] for point in points)


def test_banister_series_matches_loads(client: TestClient) -> None:
    response = client.get("/metrics/banister")

    assert response.status_code == 200
    body = response.json()
    assert body["dates"] == ["2026-10-03", "2026-10-04"]
    for freshness, performance in zip(body["freshness"], body["performance"], strict=True):
        assert performance == pytest.approx(physiology.p0 + freshness)


def test_metrics_are_empty_without_history(tmp_path: Path) -> None:
    client = _client_for(SessionStore(tmp_path / "empty.duckdb"))
    try:
        assert client.get("/metrics/acwr").json() == {"points": []}
        banister = client.get("/metrics/banister").json()
    finally:
        app.dependency_overrides.clear()

    assert banister["dates"] == []
    assert banister["fitness"] == []
    assert banister["freshness"] == []


def test_simulate_returns_trajectory(client: TestClient) -> None:
    response = client.post(
        "/simulate",
        json={
            "daily_loads": [100.0] + [0.0] * 120,
            "params": {"p0": 0.0, "k1": 1.0, "k2": 2.0, "tau1": 45.0, "tau2": 15.0},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["freshness"]) == 121
    assert body["freshness"][0] < 0.0
    assert body["freshness"][-1] > 0.0


def test_simulate_accepts_parameter_overrides(client: TestClient) -> None:
    response = client.post(
        "/simulate",
        json={
            "daily_loads": [50.0, 0.0],
            "params": {"p0": 5.0, "k1": 1.0, "k2": 2.0, "tau1": 45.0, "tau2": 15.0},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["performance"][0] == pytest.approx(5.0 + body["freshness"][0])


def test_simulate_rejects_empty_loads(client: TestClient) -> None:
    assert client.post("/simulate", json={"daily_loads": []}).status_code == 422


_DECOUPLING_START = datetime(2026, 10, 5, 7, 0, 0)


def _long_run_session() -> ParsedSession:
    samples: list[Sample] = []
    elapsed = 0.0
    for km, speed in ((0, 3.0), (1, 2.7)):
        for i in range(10):
            samples.append(
                Sample(
                    timestamp=_DECOUPLING_START + timedelta(seconds=elapsed),
                    elapsed_s=elapsed,
                    hr=150,
                    speed_mps=speed,
                    distance_m=km * 1000.0 + i * 100.0,
                    is_valid=True,
                )
            )
            elapsed += 1.0
    return ParsedSession(
        metadata=SessionMetadata(
            sport="running",
            sub_sport="street",
            start_time=_DECOUPLING_START,
            duration_s=elapsed,
        ),
        samples=samples,
    )


def test_decoupling_returns_per_km_efficiency(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "decoupling.duckdb")
    store.save_session("longrun", _long_run_session(), "data/raw/longrun.fit")
    client = _client_for(store)
    try:
        response = client.get("/metrics/decoupling/longrun")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["efficiency_per_km"] == pytest.approx([0.02, 0.018])
    assert body["decoupling_pct"] == pytest.approx(10.0)


def test_decoupling_without_distance_is_empty(client: TestClient) -> None:
    body = client.get("/metrics/decoupling/run1").json()

    assert body["efficiency_per_km"] == []
    assert body["decoupling_pct"] is None


def test_decoupling_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.get("/metrics/decoupling/missing").status_code == 404


def test_taper_merges_history_and_planned_sessions(client: TestClient) -> None:
    sessions = [
        {"date": "2026-10-05", "distance_km": 10.0, "pace_min_per_km": 5.0, "rpe": 6.0},
        {"date": "2026-10-07", "distance_km": 5.0, "pace_min_per_km": 6.0, "rpe": 4.0},
    ]
    response = client.post("/simulate/taper", json={"sessions": sessions})

    assert response.status_code == 200
    body = response.json()
    assert body["dates"] == [
        "2026-10-03",
        "2026-10-04",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    ]
    assert body["history_end_index"] == 1
    assert len(body["freshness"]) == 5


def test_taper_without_sessions_returns_history(client: TestClient) -> None:
    body = client.post("/simulate/taper", json={"sessions": []}).json()

    assert body["dates"] == ["2026-10-03", "2026-10-04"]
    assert body["history_end_index"] == 1


def test_taper_without_history_marks_no_boundary(tmp_path: Path) -> None:
    client = _client_for(SessionStore(tmp_path / "empty.duckdb"))
    sessions = [
        {"date": "2026-10-05", "distance_km": 10.0, "pace_min_per_km": 5.0, "rpe": 6.0},
    ]
    try:
        response = client.post("/simulate/taper", json={"sessions": sessions})
    finally:
        app.dependency_overrides.clear()

    assert response.json()["dates"] == ["2026-10-05"]
    assert response.json()["history_end_index"] == -1


def test_taper_rejects_invalid_session(client: TestClient) -> None:
    sessions = [
        {"date": "2026-10-05", "distance_km": 0.0, "pace_min_per_km": 5.0, "rpe": 6.0},
    ]

    assert client.post("/simulate/taper", json={"sessions": sessions}).status_code == 422


def test_calibration_falls_back_to_priors_without_observations(client: TestClient) -> None:
    body = client.get("/metrics/calibration").json()

    assert body["calibrated"] is False
    assert body["observations"] == 0
    assert body["params"] == body["priors"]
    assert body["cv_rmse"] is None
    assert body["priors"]["k1"] == pytest.approx(physiology.k_1)
    assert body["priors"]["k2"] == pytest.approx(physiology.k_2)


def test_ekf_alias_still_returns_calibration(client: TestClient) -> None:
    body = client.get("/metrics/ekf").json()

    assert body["params"] == body["priors"]


def _timed_run(start: datetime, distance_m: float = 10_000.0) -> ParsedSession:
    return ParsedSession(
        metadata=SessionMetadata(
            sport="running",
            sub_sport="street",
            start_time=start,
            duration_s=3000.0,
            distance_m=distance_m,
        ),
        samples=[],
    )


def test_running_baseline_is_null_without_distance(client: TestClient) -> None:
    assert client.get("/metrics/running-baseline").json() is None


def test_running_baseline_from_history(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "baseline.duckdb")
    for index in range(8):
        start = datetime(2026, 11, 17, 7, 0, 0) + timedelta(days=3 * index)
        exercise_id = f"base{index}"
        store.save_session(exercise_id, _timed_run(start), f"data/raw/{exercise_id}.fit")
        store.set_rpe(exercise_id, 6.0)
    client = _client_for(store)
    try:
        body = client.get("/metrics/running-baseline").json()
    finally:
        app.dependency_overrides.clear()

    assert body["weekly_km"] == pytest.approx(20.0)
    assert body["runs_per_week"] == 2
    assert body["pace_min_per_km"] == pytest.approx(5.0)
    assert body["rpe"] == pytest.approx(6.0)
    assert body["sessions"] == 8
    assert body["weeks"] == 4


def test_taper_plan_projects_to_race_day(client: TestClient) -> None:
    body = client.post(
        "/simulate/taper/plan",
        json={
            "race_date": "2026-12-13",
            "base_weekly_km": 40.0,
            "pace_min_per_km": 5.5,
            "runs_per_week": 3,
            "rpe": 6.0,
            "taper_weeks": 3,
        },
    ).json()

    assert len(body["sessions"]) == 8
    assert [week["sessions"] for week in body["weeks"]] == [3, 3, 2]
    distances = [week["distance_km"] for week in body["weeks"]]
    assert distances[0] > distances[1] > distances[2]
    assert body["simulation"]["dates"][-1] == "2026-12-13"
    assert body["simulation"]["dates"][body["race_index"]] == "2026-12-13"
    assert body["simulation"]["history_end_index"] == 1
    assert body["race_freshness"] is not None
    assert body["peak_freshness_date"] is not None
    assert body["peak_freshness"] is not None


def test_taper_plan_rejects_race_in_the_past(client: TestClient) -> None:
    response = client.post(
        "/simulate/taper/plan",
        json={
            "race_date": "2026-10-03",
            "base_weekly_km": 40.0,
            "pace_min_per_km": 5.5,
        },
    )

    assert response.status_code == 422


def test_taper_plan_requires_positive_volume(client: TestClient) -> None:
    response = client.post(
        "/simulate/taper/plan",
        json={
            "race_date": "2026-12-13",
            "base_weekly_km": 0.0,
            "pace_min_per_km": 5.5,
        },
    )

    assert response.status_code == 422
