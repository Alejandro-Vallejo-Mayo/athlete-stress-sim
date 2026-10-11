"""Tests for the dashboard fitness-fatigue chart and ACWR gauge builders."""

from __future__ import annotations

from datetime import date

import pytest

from athlete_stress_sim.backend.schemas.metrics import (
    AcwrPoint,
    BanisterSeriesResponse,
    DecouplingResponse,
    TaperSimulationResponse,
)
from athlete_stress_sim.core.metrics.acwr import RiskZone
from athlete_stress_sim.frontend.components.acwr_gauge import ZONE_META, build_acwr_gauge
from athlete_stress_sim.frontend.components.decoupling import (
    build_decoupling_figure,
    decoupling_status_text,
)
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure
from athlete_stress_sim.frontend.components.simulator import build_taper_figure, sessions_from_store

_DAY = date(2026, 10, 4)


def _series() -> BanisterSeriesResponse:
    return BanisterSeriesResponse(
        dates=[date(2026, 10, 3), _DAY],
        fitness=[10.0, 12.0],
        fatigue=[4.0, 5.0],
        performance=[6.0, 7.0],
        freshness=[6.0, 7.0],
    )


def _point(acwr: float, zone: RiskZone) -> AcwrPoint:
    return AcwrPoint(date=_DAY, acute=1.0, chronic=1.0, acwr=acwr, zone=zone)


def test_fitness_figure_has_three_series() -> None:
    figure = build_fitness_figure(_series())

    assert [trace.name for trace in figure.data] == ["Fitness", "Fatigue", "Freshness (TSB)"]
    assert [float(value) for value in figure.data[0].y] == [10.0, 12.0]
    assert [float(value) for value in figure.data[2].y] == [6.0, 7.0]


def test_fitness_figure_empty_shows_placeholder() -> None:
    figure = build_fitness_figure(BanisterSeriesResponse())

    assert len(figure.data) == 0
    assert figure.layout.annotations[0].text == "No data yet."


def test_acwr_gauge_uses_latest_point() -> None:
    figure = build_acwr_gauge([_point(1.0, RiskZone.SWEET_SPOT), _point(1.6, RiskZone.DANGER)])
    trace = figure.data[0]

    assert trace.type == "indicator"
    assert trace.value == pytest.approx(1.6)
    assert trace.title.text == "ACWR - Danger"


def test_acwr_gauge_has_four_zone_bands() -> None:
    figure = build_acwr_gauge([_point(1.0, RiskZone.SWEET_SPOT)])
    steps = figure.data[0].gauge.steps

    assert len(steps) == 4
    assert list(steps[0].range) == [0.0, 0.8]
    assert list(steps[-1].range) == [1.5, 2.0]


def test_acwr_gauge_empty_shows_placeholder() -> None:
    figure = build_acwr_gauge([])

    assert len(figure.data) == 0
    assert figure.layout.annotations[0].text == "No data yet."


def test_zone_meta_covers_all_zones() -> None:
    assert set(ZONE_META) == set(RiskZone)


def test_taper_figure_splits_history_and_forecast() -> None:
    response = TaperSimulationResponse(
        dates=[date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)],
        fitness=[1.0, 2.0, 3.0],
        fatigue=[1.0, 2.0, 3.0],
        performance=[0.0, 0.0, 0.0],
        freshness=[0.0, 0.0, 0.0],
        history_end_index=1,
    )

    figure = build_taper_figure(response)

    assert len(figure.data) == 6
    assert len(figure.layout.shapes) == 1


def test_taper_figure_empty_shows_placeholder() -> None:
    figure = build_taper_figure(TaperSimulationResponse())

    assert len(figure.data) == 0
    assert figure.layout.annotations[0].text == "No data yet."


def test_decoupling_figure_has_one_bar_per_km() -> None:
    response = DecouplingResponse(
        exercise_id="run1", efficiency_per_km=[0.02, 0.018], decoupling_pct=10.0
    )

    figure = build_decoupling_figure(response)

    assert len(figure.data) == 1
    assert list(figure.data[0].x) == [1, 2]
    assert [float(value) for value in figure.data[0].y] == [0.02, 0.018]
    assert figure.layout.title.text == "Efficiency factor per kilometre"


def test_decoupling_figure_empty_shows_placeholder() -> None:
    figure = build_decoupling_figure(DecouplingResponse(exercise_id="run1"))

    assert len(figure.data) == 0
    assert figure.layout.annotations[0].text == "No data yet."


def test_decoupling_status_text_without_data() -> None:
    response = DecouplingResponse(exercise_id="run1")

    assert decoupling_status_text(response) == "Not enough data to compute decoupling."


def test_sessions_from_store_parses_and_skips_invalid() -> None:
    data = [
        {"date": "2026-10-05", "distance_km": 10.0, "pace_min_per_km": 5.0, "rpe": 6.0},
        {"date": "not-a-date", "distance_km": 10.0, "pace_min_per_km": 5.0, "rpe": 6.0},
        {"distance_km": 10.0},
    ]

    sessions = sessions_from_store(data)

    assert len(sessions) == 1
    assert sessions[0].distance_km == 10.0
