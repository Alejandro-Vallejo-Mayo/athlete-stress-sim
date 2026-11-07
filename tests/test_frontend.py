"""Tests for the dashboard readiness heuristic and the metrics API client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import httpx2
import pytest

from athlete_stress_sim.backend.schemas.metrics import PlannedSession, TaperPlanRequest
from athlete_stress_sim.core.models.banister import BanisterParams
from athlete_stress_sim.frontend import app as frontend_app
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.readiness import Readiness, readiness_level

Handler = Callable[[httpx2.Request], httpx2.Response]


def _client(handler: Handler) -> MetricsClient:
    return MetricsClient(
        "http://backend:8000",
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def _session() -> PlannedSession:
    return PlannedSession(date=date(2026, 10, 5), distance_km=10.0, pace_min_per_km=5.0, rpe=6.0)


@pytest.mark.parametrize(
    ("freshness", "expected"),
    [
        (10.0, Readiness.READY),
        (0.0, Readiness.READY),
        (-1.0, Readiness.CAUTION),
        (-5.0, Readiness.CAUTION),
        (-5.1, Readiness.REST),
    ],
)
def test_readiness_level_bands(freshness: float, expected: Readiness) -> None:
    assert readiness_level(freshness) is expected


def test_metrics_client_parses_banister() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/banister"
        return httpx2.Response(
            200,
            json={
                "dates": ["2026-10-03"],
                "fitness": [10.0],
                "fatigue": [4.0],
                "performance": [2.0],
                "freshness": [6.0],
            },
        )

    series = _client(handler).get_banister()

    assert series.freshness == [6.0]


def test_metrics_client_parses_acwr() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "points": [
                    {
                        "date": "2026-10-03",
                        "acute": 1.0,
                        "chronic": 1.0,
                        "acwr": 1.0,
                        "zone": "sweet_spot",
                    }
                ]
            },
        )

    points = _client(handler).get_acwr().points

    assert points[0].zone is not None
    assert points[0].zone.value == "sweet_spot"


def test_metrics_client_raises_when_unreachable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    with pytest.raises(MetricsClientError):
        _client(handler).get_banister()


def test_metrics_client_raises_on_error_status() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503, text="unavailable")

    with pytest.raises(MetricsClientError):
        _client(handler).get_acwr()


def test_metrics_client_gets_running_exercises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/exercises"
        assert request.url.params.get("kind") == "run"
        return httpx2.Response(200, json=[{"exercise_id": "run1", "sport": "running"}])

    exercises = _client(handler).get_exercises("run")

    assert exercises[0].exercise_id == "run1"


def test_metrics_client_gets_decoupling() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/decoupling/run1"
        return httpx2.Response(
            200,
            json={
                "exercise_id": "run1",
                "efficiency_per_km": [0.02, 0.018],
                "decoupling_pct": 10.0,
            },
        )

    response = _client(handler).get_decoupling("run1")

    assert response.decoupling_pct == pytest.approx(10.0)


def test_metrics_client_gets_ekf() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/ekf"
        return httpx2.Response(
            200,
            json={
                "params": {"p0": 0.0, "k1": 1.5, "k2": 2.5, "tau1": 40.0, "tau2": 12.0},
                "priors": {"p0": 0.0, "k1": 1.0, "k2": 2.0, "tau1": 45.0, "tau2": 15.0},
                "calibrated": True,
                "observations": 12,
                "r_squared": 0.6,
                "baseline_efficiency": 0.02,
            },
        )

    response = _client(handler).get_ekf()

    assert response.calibrated is True
    assert response.params.k1 == pytest.approx(1.5)


def test_metrics_client_syncs() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/sync"
        return httpx2.Response(
            200,
            json={
                "sync": {
                    "listed": 2,
                    "downloaded": 1,
                    "skipped": 1,
                    "failed": 0,
                    "errors": [],
                },
                "parse": {"parsed": 1, "skipped": 0, "failed": 0, "errors": []},
            },
        )

    result = _client(handler).sync()

    assert result.sync.downloaded == 1
    assert result.parse.parsed == 1


def test_metrics_client_sets_rpe() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/exercises/gym1/rpe"
        captured.update(json.loads(request.content))
        return httpx2.Response(200, json={"exercise_id": "gym1", "rpe": 7.0, "load": 420.0})

    exercise = _client(handler).set_rpe("gym1", 7.0)

    assert exercise.rpe == pytest.approx(7.0)
    assert captured["rpe"] == pytest.approx(7.0)


def test_metrics_client_gets_running_baseline() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/running-baseline"
        return httpx2.Response(
            200,
            json={
                "weekly_km": 20.0,
                "runs_per_week": 2,
                "pace_min_per_km": 5.0,
                "rpe": 6.0,
                "sessions": 8,
                "weeks": 4,
            },
        )

    baseline = _client(handler).get_running_baseline()

    assert baseline is not None
    assert baseline.weekly_km == pytest.approx(20.0)


def test_metrics_client_running_baseline_null() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"null")

    assert _client(handler).get_running_baseline() is None


def test_metrics_client_posts_taper_plan() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/simulate/taper/plan"
        captured.update(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "sessions": [],
                "weeks": [],
                "simulation": {
                    "dates": [],
                    "fitness": [],
                    "fatigue": [],
                    "performance": [],
                    "freshness": [],
                    "history_end_index": -1,
                },
                "race_date": "2026-12-13",
                "race_index": 0,
                "race_freshness": 1.0,
                "peak_freshness_date": "2026-12-13",
                "peak_freshness": 1.0,
            },
        )

    request = TaperPlanRequest(
        race_date=date(2026, 12, 13),
        base_weekly_km=40.0,
        pace_min_per_km=5.5,
    )
    response = _client(handler).post_taper_plan(request)

    assert response.race_date == date(2026, 12, 13)
    assert captured["base_weekly_km"] == pytest.approx(40.0)


def test_metrics_client_posts_taper_with_params() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.update(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "dates": [],
                "fitness": [],
                "fatigue": [],
                "performance": [],
                "freshness": [],
                "history_end_index": -1,
            },
        )

    params = BanisterParams(p0=0.0, k1=1.5, k2=2.5, tau1=40.0, tau2=12.0)
    _client(handler).post_taper([_session()], params)

    assert captured["params"] == params.model_dump(mode="json")


def test_metrics_client_posts_taper() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/simulate/taper"
        return httpx2.Response(
            200,
            json={
                "dates": ["2026-10-05"],
                "fitness": [1.0],
                "fatigue": [2.0],
                "performance": [-1.0],
                "freshness": [-1.0],
                "history_end_index": -1,
            },
        )

    sessions = [_session()]
    response = _client(handler).post_taper(sessions)

    assert response.dates == [date(2026, 10, 5)]


def test_metrics_client_post_taper_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, text="boom")

    with pytest.raises(MetricsClientError):
        _client(handler).post_taper([_session()])


def test_frontend_app_imports() -> None:
    assert frontend_app.app.title == "Athlete Stress Sim"
