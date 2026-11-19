"""Pending gym RPE badge and update modal (S14, ``RF-01.4``)."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut
from athlete_stress_sim.frontend.theme import COLORS, surface_style

_HIDDEN = {"display": "none"}
_VISIBLE = {"display": "flex"}
_SECONDS_PER_MINUTE = 60.0


def pending_gym_sessions(exercises: list[ExerciseOut]) -> list[ExerciseOut]:
    """Return the gym sessions that still have no session-RPE.

    Args:
        exercises: Gym exercises as returned by the backend.

    Returns:
        The exercises whose ``rpe`` is ``None``.
    """
    return [exercise for exercise in exercises if exercise.rpe is None]


def rpe_session_options(exercises: list[ExerciseOut]) -> list[dict[str, str]]:
    """Build the select options used to pick a pending gym session.

    Args:
        exercises: Pending gym exercises.

    Returns:
        One ``{"value", "label"}`` option per exercise, ordered as given.
    """
    return [
        {"value": exercise.exercise_id, "label": _session_label(exercise)} for exercise in exercises
    ]


def rpe_pending_style(count: int) -> dict[str, str]:
    """Return the button style: visible only while sessions are pending."""
    return _VISIBLE if count > 0 else _HIDDEN


def rpe_pending_children(count: int) -> object:
    """Build the pending-RPE button contents with a count badge."""
    return dmc.Group(
        [
            dmc.Text("RPE pending", size="sm"),
            dmc.Badge(str(count), color="orange", variant="filled"),
        ],
        gap=6,
    )


def rpe_pending_message(count: int) -> str:
    """Describe how many gym sessions still need an RPE."""
    if count == 0:
        return "All gym sessions have RPE logged."
    noun = "session" if count == 1 else "sessions"
    verb = "needs" if count == 1 else "need"
    return f"{count} gym {noun} {verb} an RPE. Load and ACWR may be underestimated."


def rpe_pending_card() -> dmc.Paper:
    """Build the Today card that surfaces pending gym RPE work."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(
                    "Gym RPE",
                    size="xs",
                    fw=600,
                    tt="uppercase",
                    style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
                ),
                dmc.Text(
                    "Checking pending RPE...",
                    id="rpe-pending-text",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
                dmc.Button(
                    "Review RPE",
                    id="rpe-card-open",
                    variant="light",
                    size="xs",
                    style={"display": "none"},
                ),
            ],
            gap="sm",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def rpe_modal() -> dmc.Modal:
    """Build the modal used to record a pending gym session's RPE."""
    return dmc.Modal(
        id="rpe-modal",
        title="Update gym RPE",
        opened=False,
        centered=True,
        children=dmc.Stack(
            [
                dmc.Text(
                    "Gym sessions without RPE are excluded from load and ACWR.",
                    c="dimmed",
                    size="sm",
                ),
                dmc.Select(
                    id="rpe-session-select",
                    label="Gym session",
                    placeholder="Select a session",
                    data=[],
                    nothingFoundMessage="No pending sessions",
                ),
                dmc.NumberInput(
                    id="rpe-value",
                    label="RPE (0-10)",
                    min=0.0,
                    max=10.0,
                    step=0.5,
                ),
                dmc.Text(id="rpe-feedback", size="sm", **{"aria-live": "polite"}),
                dmc.Group(
                    [
                        dmc.Button("Save & next", id="rpe-save", variant="light"),
                        dmc.Button("Save & close", id="rpe-apply", variant="filled"),
                        dmc.Button("Cancel", id="rpe-cancel", variant="subtle"),
                    ],
                    justify="flex-end",
                    wrap="wrap",
                ),
            ],
            gap="sm",
        ),
    )


def _session_label(exercise: ExerciseOut) -> str:
    when = exercise.start_time.date().isoformat() if exercise.start_time else "unknown"
    if exercise.duration_s is None:
        duration = "no duration"
    else:
        duration = f"{exercise.duration_s / _SECONDS_PER_MINUTE:.0f} min"
    return f"{when} · {duration}"
