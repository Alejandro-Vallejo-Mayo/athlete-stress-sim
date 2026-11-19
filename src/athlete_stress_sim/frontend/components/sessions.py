"""Recent sessions card for the Trends view."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut
from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.frontend.theme import COLORS, surface_style

_RECENT_LIMIT = 8
_SECONDS_PER_MINUTE = 60.0
_METERS_PER_KM = 1000.0


def recent_sessions_panel(exercises: list[ExerciseOut]) -> dmc.Paper:
    """Build the recent sessions list with RPE status and a review action."""
    recent = exercises[:_RECENT_LIMIT]
    pending = any(
        exercise.rpe is None and is_strength(exercise.sport, exercise.sub_sport)
        for exercise in exercises
    )
    rows = [_session_row(exercise) for exercise in recent]
    content: list[object] = [
        dmc.Stack(
            [
                dmc.Text("Recent sessions", fw=600, size="lg", style={"color": COLORS["text"]}),
                dmc.Text(
                    "Latest runs and gym sessions. Gym sessions need an RPE to count toward load.",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
            ],
            gap=0,
        )
    ]
    if rows:
        content.append(dmc.Stack(rows, gap="xs"))
    else:
        content.append(
            dmc.Text("No sessions yet.", size="sm", style={"color": COLORS["text_muted"]})
        )
    content.append(
        dmc.Button(
            "Review RPE",
            id="sessions-rpe-open",
            variant="light",
            size="xs",
            disabled=not pending,
        )
    )
    return dmc.Paper(
        dmc.Stack(content, gap="md"),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def _session_row(exercise: ExerciseOut) -> dmc.Group:
    strength = is_strength(exercise.sport, exercise.sub_sport)
    return dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Text(
                        f"{_date_label(exercise)} · {'Gym' if strength else 'Run'}",
                        size="sm",
                        fw=600,
                        style={"color": COLORS["text"]},
                    ),
                    dmc.Text(
                        _detail_label(exercise),
                        size="xs",
                        style={"color": COLORS["text_muted"]},
                    ),
                ],
                gap=0,
            ),
            _rpe_badge(exercise, strength),
        ],
        justify="space-between",
        wrap="nowrap",
        gap="sm",
    )


def _rpe_badge(exercise: ExerciseOut, strength: bool) -> dmc.Badge:
    if exercise.rpe is not None:
        return dmc.Badge(
            f"RPE {exercise.rpe:.0f}",
            size="sm",
            style={
                "backgroundColor": f"{COLORS['ready']}22",
                "border": f"1px solid {COLORS['ready']}55",
                "color": COLORS["ready"],
            },
        )
    if strength:
        return dmc.Badge(
            "RPE pending",
            size="sm",
            style={
                "backgroundColor": f"{COLORS['caution']}22",
                "border": f"1px solid {COLORS['caution']}55",
                "color": COLORS["caution"],
            },
        )
    return dmc.Badge(
        "No RPE",
        size="sm",
        variant="light",
        style={"color": COLORS["text_muted"]},
    )


def _date_label(exercise: ExerciseOut) -> str:
    if exercise.start_time is None:
        return "Unknown date"
    return exercise.start_time.strftime("%b %d")


def _detail_label(exercise: ExerciseOut) -> str:
    parts: list[str] = []
    if exercise.distance_m:
        parts.append(f"{exercise.distance_m / _METERS_PER_KM:.1f} km")
    if exercise.duration_s:
        parts.append(f"{exercise.duration_s / _SECONDS_PER_MINUTE:.0f} min")
    if exercise.avg_hr:
        parts.append(f"{exercise.avg_hr} bpm")
    return " · ".join(parts) if parts else "No telemetry"


def edit_session_options(exercises: list[ExerciseOut]) -> list[dict[str, str]]:
    """Build the session selector options for the manual editor."""
    return [
        {"value": exercise.exercise_id, "label": _edit_label(exercise)} for exercise in exercises
    ]


def session_editor_card() -> dmc.Paper:
    """Build the Today card that opens the manual session editor."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(
                    "Session data",
                    size="xs",
                    fw=600,
                    tt="uppercase",
                    style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
                ),
                dmc.Text(
                    "Correct the date, distance, duration or heart rate of any session.",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
                dmc.Select(
                    id="edit-session-select",
                    label="Session",
                    placeholder="Select a session",
                    data=[],
                    searchable=True,
                ),
                dmc.Text(
                    "Select a session to edit.",
                    id="edit-session-status",
                    size="xs",
                    style={"color": COLORS["text_muted"]},
                ),
                dmc.Button(
                    "Edit session",
                    id="edit-session-open",
                    variant="light",
                    size="xs",
                ),
            ],
            gap="sm",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def session_edit_modal() -> dmc.Modal:
    """Build the modal used to correct one session's metadata."""
    return dmc.Modal(
        id="session-edit-modal",
        title="Edit session",
        opened=False,
        centered=True,
        children=dmc.Stack(
            [
                dmc.DateTimePicker(
                    id="edit-start-time",
                    label="Start time",
                    value=None,
                    clearable=False,
                ),
                dmc.SimpleGrid(
                    [
                        dmc.NumberInput(
                            id="edit-distance",
                            label="Distance (km)",
                            min=0.0,
                            step=0.1,
                            decimalScale=2,
                        ),
                        dmc.NumberInput(
                            id="edit-duration",
                            label="Duration (min)",
                            min=0.0,
                            step=1.0,
                            decimalScale=1,
                        ),
                        dmc.NumberInput(
                            id="edit-avg-hr",
                            label="Average HR (bpm)",
                            min=0,
                            step=1,
                        ),
                        dmc.NumberInput(
                            id="edit-max-hr",
                            label="Max HR (bpm)",
                            min=0,
                            step=1,
                        ),
                    ],
                    cols={"base": 1, "sm": 2},
                    spacing="sm",
                ),
                dmc.Text(id="edit-session-feedback", size="sm", **{"aria-live": "polite"}),
                dmc.Group(
                    [
                        dmc.Button("Save changes", id="edit-session-save", variant="filled"),
                        dmc.Button("Cancel", id="edit-session-cancel", variant="subtle"),
                    ],
                    justify="flex-end",
                    wrap="wrap",
                ),
            ],
            gap="sm",
        ),
    )


def _edit_label(exercise: ExerciseOut) -> str:
    kind = "Gym" if is_strength(exercise.sport, exercise.sub_sport) else "Run"
    return f"{_date_label(exercise)} · {kind} · {_detail_label(exercise)}"
