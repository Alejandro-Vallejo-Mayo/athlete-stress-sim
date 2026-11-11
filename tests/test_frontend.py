"""Tests for the dashboard readiness heuristic and the metrics API client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import dash_mantine_components as dmc
import httpx2
import pytest

from athlete_stress_sim.backend.schemas.metrics import PlannedSession, TaperPlanRequest
from athlete_stress_sim.backend.schemas.prediction import RacePredictionRequest
from athlete_stress_sim.core.metrics.race_prediction import PredictionModel
from athlete_stress_sim.core.models.banister import BanisterParams
from athlete_stress_sim.frontend import app as frontend_app
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.readiness import (
    Readiness,
    assess_readiness,
    freshness_percentile,
    readiness_level,
)

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


def test_freshness_percentile_counts_history_at_or_below() -> None:
    history = [float(value) for value in range(20)]

    assert freshness_percentile(5.0, history) == pytest.approx(0.3)
    assert freshness_percentile(100.0, history) == pytest.approx(1.0)


def test_assess_readiness_uses_recent_history() -> None:
    history = [float(value) for value in range(20)]

    ready, ready_percentile = assess_readiness(19.0, history)
    caution, caution_percentile = assess_readiness(5.0, history)
    rest, rest_percentile = assess_readiness(1.0, history)

    assert ready is Readiness.READY
    assert ready_percentile == pytest.approx(1.0)
    assert caution is Readiness.CAUTION
    assert caution_percentile == pytest.approx(0.3)
    assert rest is Readiness.REST
    assert rest_percentile == pytest.approx(0.1)


def test_assess_readiness_falls_back_with_short_history() -> None:
    readiness, percentile = assess_readiness(10.0, [1.0, 2.0, 3.0])
    rest, _ = assess_readiness(-10.0, [1.0, 2.0, 3.0])

    assert readiness is Readiness.READY
    assert percentile is None
    assert rest is Readiness.REST


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


def test_metrics_client_gets_calibration() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/calibration"
        return httpx2.Response(
            200,
            json={
                "params": {"p0": 0.0, "k1": 1.5, "k2": 2.5, "tau1": 40.0, "tau2": 12.0},
                "priors": {"p0": 0.0, "k1": 1.0, "k2": 2.0, "tau1": 45.0, "tau2": 15.0},
                "calibrated": True,
                "observations": 12,
                "r_squared": 0.6,
                "baseline_efficiency": 0.02,
                "cv_rmse": 0.001,
                "prior_cv_rmse": 0.002,
                "cv_improvement": 0.5,
            },
        )

    response = _client(handler).get_calibration()

    assert response.calibrated is True
    assert response.params.k1 == pytest.approx(1.5)
    assert response.cv_improvement == pytest.approx(0.5)


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


def test_metrics_client_gets_best_efforts() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/best-efforts"
        return httpx2.Response(
            200,
            json=[
                {
                    "distance_km": 5.0,
                    "time_s": 1600.0,
                    "day": "2026-10-01",
                    "tier": "race",
                    "source": "training",
                }
            ],
        )

    efforts = _client(handler).get_best_efforts()

    assert efforts[0].distance_km == pytest.approx(5.0)
    assert efforts[0].tier.value == "race"


def test_metrics_client_predicts_race() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/metrics/race-prediction"
        captured.update(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "distance_km": 21.0975,
                "predicted_time_s": 7200.0,
                "predicted_pace_s_per_km": 341.3,
                "fast_time_s": 7000.0,
                "slow_time_s": 7400.0,
                "model": "critical_speed",
                "confidence": "high",
                "efforts": [],
                "notes": ["Ready."],
            },
        )

    request = RacePredictionRequest(
        distance_km=21.0975,
        model=PredictionModel.AUTO,
    )
    response = _client(handler).predict_race(request)

    assert response.model is PredictionModel.CRITICAL_SPEED
    assert response.predicted_time_s == pytest.approx(7200.0)
    assert captured["distance_km"] == pytest.approx(21.0975)


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


def _walk(component: object):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "_prop_names"):
                yield from _walk(child)
    elif hasattr(children, "_prop_names"):
        yield from _walk(children)


def test_frontend_layout_has_three_tabs_and_shared_ids() -> None:
    components = list(_walk(frontend_app.app.layout))

    tabs = [component for component in components if isinstance(component, dmc.Tabs)]
    tab_values = {component.value for component in components if isinstance(component, dmc.TabsTab)}
    ids = {
        component.id for component in components if isinstance(getattr(component, "id", None), str)
    }

    assert tabs and tabs[0].value == "today"
    assert tab_values == {"today", "trends", "plan"}
    assert {
        "status-panel",
        "acwr-risk-panel",
        "freshness-panel",
        "quick-stats",
        "fitness-chart",
        "refresh-btn",
        "rpe-pending-btn",
        "rpe-pending-text",
        "rpe-card-open",
        "dashboard-alert",
        "sim-chart",
        "race-chart",
    } <= ids


def test_frontend_uses_the_shared_mantine_theme() -> None:
    layout = frontend_app.app.layout

    assert layout.theme["primaryColor"] == "cyan"
    assert layout.theme["defaultRadius"] == "md"


def _dashboard_handler(empty: bool = False) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/metrics/banister":
            payload = (
                {
                    "dates": [],
                    "fitness": [],
                    "fatigue": [],
                    "performance": [],
                    "freshness": [],
                }
                if empty
                else {
                    "dates": ["2026-10-03", "2026-10-04"],
                    "fitness": [10.0, 12.0],
                    "fatigue": [4.0, 5.0],
                    "performance": [6.0, 7.0],
                    "freshness": [6.0, 7.0],
                }
            )
            return httpx2.Response(200, json=payload)
        if request.url.path == "/metrics/acwr":
            return httpx2.Response(
                200,
                json={"points": []}
                if empty
                else {
                    "points": [
                        {
                            "date": "2026-10-04",
                            "acute": 1.0,
                            "chronic": 1.0,
                            "acwr": 1.0,
                            "zone": "sweet_spot",
                        }
                    ]
                },
            )
        if request.url.path == "/exercises":
            return httpx2.Response(200, json=[])
        raise AssertionError(f"Unexpected request: {request.url}")

    return handler


def test_load_dashboard_builds_today_panels() -> None:
    dashboard = frontend_app._load_dashboard(_client(_dashboard_handler()), None)

    assert len(dashboard) == 8
    assert dashboard[-1] is None


def test_load_dashboard_returns_no_data_alert() -> None:
    dashboard = frontend_app._load_dashboard(_client(_dashboard_handler(empty=True)), None)

    alert = dashboard[-1]
    assert isinstance(alert, dmc.Alert)
    assert alert.title == "No data"


def test_empty_dashboard_returns_offline_alert() -> None:
    dashboard = frontend_app._empty_dashboard()

    alert = dashboard[-1]
    assert isinstance(alert, dmc.Alert)
    assert alert.title == "Backend offline"
