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
from athlete_stress_sim.frontend.components.acwr_gauge import (
    ZONE_META,
    acwr_risk_panel,
    build_acwr_risk_figure,
)
from athlete_stress_sim.frontend.components.decoupling import (
    build_decoupling_figure,
    decoupling_status_text,
)
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure
from athlete_stress_sim.frontend.components.freshness_chart import (
    build_freshness_figure,
    freshness_panel,
)
from athlete_stress_sim.frontend.components.quick_stats import quick_stats_panel
from athlete_stress_sim.frontend.components.simulator import build_taper_figure, sessions_from_store
from athlete_stress_sim.frontend.theme import COLORS

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


def test_acwr_risk_figure_marks_the_latest_point() -> None:
    figure = build_acwr_risk_figure(
        [_point(1.0, RiskZone.SWEET_SPOT), _point(1.6, RiskZone.DANGER)]
    )
    marker = figure.layout.shapes[-1]

    assert marker.type == "line"
    assert marker.x0 == pytest.approx(1.6)
    assert marker.x1 == pytest.approx(1.6)
    assert figure.layout.annotations[-1].text == "1.60"


def test_acwr_risk_figure_has_four_zone_bands() -> None:
    figure = build_acwr_risk_figure([_point(1.0, RiskZone.SWEET_SPOT)])
    bands = [shape for shape in figure.layout.shapes if shape.type == "rect"]

    assert len(bands) == 4
    assert (bands[0].x0, bands[0].x1) == (0.0, 0.8)
    assert (bands[-1].x0, bands[-1].x1) == (1.5, 2.0)


def test_acwr_risk_figure_empty_shows_placeholder() -> None:
    figure = build_acwr_risk_figure([])

    assert len(figure.data) == 0
    assert figure.layout.annotations[0].text == "No data yet."


def test_acwr_risk_panel_and_quick_stats_are_papers() -> None:
    point = _point(1.0, RiskZone.SWEET_SPOT)

    assert type(acwr_risk_panel([point])).__name__ == "Paper"
    assert type(quick_stats_panel(_series(), [point])).__name__ == "Paper"


def test_freshness_figure_and_panel() -> None:
    figure = build_freshness_figure(_series())

    assert len(figure.data) == 1
    assert figure.data[0].name == "Freshness (TSB)"
    assert figure.data[0].line.color == COLORS["freshness"]
    assert type(freshness_panel(_series())).__name__ == "Paper"


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


def test_taper_figure_marks_race_day() -> None:
    response = TaperSimulationResponse(
        dates=[date(2026, 12, 11), date(2026, 12, 12), date(2026, 12, 13)],
        fitness=[1.0, 2.0, 3.0],
        fatigue=[1.0, 2.0, 3.0],
        performance=[0.0, 0.0, 0.0],
        freshness=[0.0, 0.0, 0.0],
        history_end_index=1,
    )

    figure = build_taper_figure(response, race_date=date(2026, 12, 13))

    assert len(figure.layout.shapes) == 2
    assert figure.layout.annotations[-1].text == "Race day"


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


def test_fitness_figure_uses_theme_series_colors() -> None:
    figure = build_fitness_figure(_series())

    assert figure.data[0].line.color == COLORS["fitness"]
    assert figure.data[1].line.color == COLORS["fatigue"]
    assert figure.data[2].line.color == COLORS["freshness"]


def test_acwr_zone_metadata_uses_theme_colors() -> None:
    assert ZONE_META[RiskZone.DANGER].color == COLORS["danger"]
    assert ZONE_META[RiskZone.SWEET_SPOT].color == COLORS["ready"]
