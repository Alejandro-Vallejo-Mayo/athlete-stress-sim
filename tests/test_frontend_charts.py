"""Tests for the dashboard fitness-fatigue chart and ACWR gauge builders."""

from __future__ import annotations

from datetime import date

import pytest

from athlete_stress_sim.backend.schemas.metrics import AcwrPoint, BanisterSeriesResponse
from athlete_stress_sim.core.metrics.acwr import RiskZone
from athlete_stress_sim.frontend.components.acwr_gauge import ZONE_META, build_acwr_gauge
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure

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
