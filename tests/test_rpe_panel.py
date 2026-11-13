"""Tests for the pending gym RPE badge helpers (``S14``)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from dash.development.base_component import Component

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut
from athlete_stress_sim.frontend.components.rpe import (
    pending_gym_sessions,
    rpe_modal,
    rpe_pending_card,
    rpe_pending_message,
    rpe_pending_style,
    rpe_session_options,
)
from athlete_stress_sim.frontend.components.sessions import (
    recent_sessions_panel,
    session_edit_modal,
    session_editor_card,
)
from athlete_stress_sim.frontend.components.simulator import race_taper_panel, simulator_panel

_START = datetime(2026, 10, 4, 18, 0, 0)


def _exercise(
    exercise_id: str,
    *,
    rpe: float | None = None,
    duration_s: float | None = 3600.0,
    start_time: datetime | None = _START,
) -> ExerciseOut:
    return ExerciseOut(
        exercise_id=exercise_id,
        sport="training",
        sub_sport="strength_training",
        start_time=start_time,
        duration_s=duration_s,
        rpe=rpe,
    )


def test_pending_gym_sessions_filters_out_recorded_rpe() -> None:
    exercises = [
        _exercise("gym1", rpe=None),
        _exercise("gym2", rpe=7.0),
        _exercise("gym3", rpe=None),
    ]

    pending = pending_gym_sessions(exercises)

    assert [exercise.exercise_id for exercise in pending] == ["gym1", "gym3"]


def test_rpe_session_options_build_labels() -> None:
    exercises = [
        _exercise("gym1"),
        _exercise("gym2", duration_s=None, start_time=None),
    ]

    options = rpe_session_options(exercises)

    assert options[0] == {"value": "gym1", "label": "2026-10-04 · 60 min"}
    assert options[1] == {"value": "gym2", "label": "unknown · no duration"}


def test_rpe_pending_style_hides_when_empty() -> None:
    assert rpe_pending_style(0) == {"display": "none"}
    assert rpe_pending_style(2) == {"display": "flex"}


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


def test_rpe_modal_has_apply_button() -> None:
    ids = set(_by_id(rpe_modal()))

    assert {"rpe-save", "rpe-apply", "rpe-cancel", "rpe-session-select"} <= ids


def test_simulator_form_starts_empty() -> None:
    components = _by_id(simulator_panel())

    for component_id in ("sim-date", "sim-distance", "sim-pace", "sim-rpe"):
        assert getattr(components[component_id], "value", None) is None


def test_race_taper_form_starts_empty() -> None:
    components = _by_id(race_taper_panel())

    for component_id in (
        "race-date",
        "race-base-km",
        "race-runs",
        "race-pace",
        "race-rpe",
        "race-weeks",
    ):
        assert getattr(components[component_id], "value", None) is None


def test_rpe_pending_message_describes_pending_count() -> None:
    assert rpe_pending_message(0) == "All gym sessions have RPE logged."
    assert rpe_pending_message(1).startswith("1 gym session needs")
    assert "3 gym sessions" in rpe_pending_message(3)


def test_rpe_pending_card_has_a_review_action() -> None:
    ids = set(_by_id(rpe_pending_card()))

    assert {"rpe-pending-text", "rpe-card-open"} <= ids


def test_recent_sessions_panel_has_review_action() -> None:
    components = _by_id(recent_sessions_panel([_exercise("gym1"), _exercise("gym2", rpe=6.0)]))

    assert components["sessions-rpe-open"].disabled is False


def test_recent_sessions_panel_without_pending_disables_action() -> None:
    components = _by_id(recent_sessions_panel([_exercise("gym1", rpe=6.0)]))

    assert components["sessions-rpe-open"].disabled is True


def test_session_editor_card_and_modal_have_ids() -> None:
    card_ids = set(_by_id(session_editor_card()))
    modal_ids = set(_by_id(session_edit_modal()))

    assert {"edit-session-select", "edit-session-open", "edit-session-status"} <= card_ids
    assert {
        "edit-start-time",
        "edit-distance",
        "edit-duration",
        "edit-avg-hr",
        "edit-max-hr",
        "edit-session-save",
        "edit-session-cancel",
    } <= modal_ids
