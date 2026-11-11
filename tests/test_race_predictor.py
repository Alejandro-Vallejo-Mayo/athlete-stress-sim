"""Tests for the race predictor panel helpers (``RF-05.4``)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from dash.development.base_component import Component

from athlete_stress_sim.backend.schemas.prediction import EffortOut
from athlete_stress_sim.core.metrics.race_prediction import EffortTier
from athlete_stress_sim.frontend.components.race_predictor import (
    HALF_MARATHON_KM,
    effort_label,
    effort_rows,
    format_pace,
    note_rows,
    optional_float,
    preset_distance,
    race_predictor_panel,
)


def _iter_components(component: object) -> Iterator[Component]:
    if not isinstance(component, Component):
        return
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _iter_components(child)
    else:
        yield from _iter_components(children)


def _by_id(panel: Component) -> dict[str, Component]:
    return {
        component.id: component
        for component in _iter_components(panel)
        if getattr(component, "id", None) is not None
    }


def test_format_pace() -> None:
    assert format_pace(330.0) == "5:30 /km"
    assert format_pace(None) == "—"


def test_preset_distance() -> None:
    assert preset_distance("5k") == pytest.approx(5.0)
    assert preset_distance("half") == pytest.approx(HALF_MARATHON_KM)
    assert preset_distance("custom") is None
    assert preset_distance(None) is None


def test_optional_float_handles_empty_and_invalid_values() -> None:
    assert optional_float(None) is None
    assert optional_float("") is None
    assert optional_float("   ") is None
    assert optional_float("not a number") is None
    assert optional_float(float("nan")) is None
    assert optional_float("5.5") == pytest.approx(5.5)
    assert optional_float(10) == pytest.approx(10.0)


def test_effort_label_includes_intensity_and_fitness() -> None:
    effort = EffortOut(
        distance_km=5.0,
        time_s=1600.0,
        day=date(2026, 10, 1),
        relative_hr=0.8,
        tier=EffortTier.RACE,
        fitness_factor=1.05,
    )

    label = effort_label(effort)

    assert "5.00 km" in label
    assert "26:40" in label
    assert "80% HRR" in label
    assert "race" in label
    assert "fitness x1.05" in label


def test_effort_rows_handles_empty_history() -> None:
    rows = effort_rows([])

    assert len(rows) == 1
    assert "No best efforts" in rows[0].children


def test_note_rows() -> None:
    rows = note_rows(["one", "two"])

    assert [row.children for row in rows] == ["one", "two"]


def test_race_predictor_panel_defaults() -> None:
    components = _by_id(race_predictor_panel())

    assert components["race-distance-preset"].value == "half"
    assert components["race-distance-custom"].style == {"display": "none"}
    assert components["race-model"].value == "auto"
    assert components["race-exponent"].value == pytest.approx(1.06)
    assert "race-predict" in components
    assert "race-result-time" in components
    assert "race-efforts-list" in components
