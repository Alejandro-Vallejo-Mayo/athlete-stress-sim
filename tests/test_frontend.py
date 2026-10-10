"""Tests for the dashboard readiness heuristic and the metrics API client."""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from athlete_stress_sim.frontend import app as frontend_app
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.readiness import Readiness, readiness_level

Handler = Callable[[httpx2.Request], httpx2.Response]


def _client(handler: Handler) -> MetricsClient:
    return MetricsClient(
        "http://backend:8000",
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


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


def test_frontend_app_imports() -> None:
    assert frontend_app.app.title == "Athlete Stress Sim"
