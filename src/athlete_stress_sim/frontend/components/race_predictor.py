"""Race time predictor panel (``RF-05.4``)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import dash_mantine_components as dmc
from dash import html

from athlete_stress_sim.backend.schemas.prediction import EffortOut
from athlete_stress_sim.core.metrics.race_prediction import format_duration

HALF_MARATHON_KM = 21.0975
"""Default target distance in the race predictor."""

_FITNESS_EPS = 1e-6

_DISTANCE_PRESETS: dict[str, float | None] = {
    "5k": 5.0,
    "10k": 10.0,
    "half": HALF_MARATHON_KM,
    "marathon": 42.195,
    "custom": None,
}


def distance_options() -> list[dict[str, str]]:
    """Return the distance preset options for the selector."""
    return [
        {"value": "5k", "label": "5 km"},
        {"value": "10k", "label": "10 km"},
        {"value": "half", "label": "Half marathon"},
        {"value": "marathon", "label": "Marathon"},
        {"value": "custom", "label": "Custom"},
    ]


def preset_distance(preset: str | None) -> float | None:
    """Return the distance for a preset, or ``None`` for a custom distance."""
    if preset is None:
        return None
    return _DISTANCE_PRESETS.get(preset)


def optional_float(value: object) -> float | None:
    """Parse a numeric input, treating empty or invalid values as missing."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    return number if math.isfinite(number) else None


def format_pace(seconds_per_km: float | None) -> str:
    """Format a pace in seconds per kilometre as ``M:SS /km``."""
    if seconds_per_km is None:
        return "—"
    return f"{format_duration(seconds_per_km)} /km"


def effort_label(effort: EffortOut) -> str:
    """Build a compact label for one detected effort."""
    hr = "HR n/a" if effort.relative_hr is None else f"{effort.relative_hr:.0%} HRR"
    label = (
        f"{effort.distance_km:.2f} km · {format_duration(effort.time_s)} · "
        f"{hr} · {effort.tier.value}"
    )
    if abs(effort.fitness_factor - 1.0) > _FITNESS_EPS:
        label += f" · fitness x{effort.fitness_factor:.2f}"
    return label


def effort_rows(efforts: Sequence[EffortOut]) -> list[dmc.Text]:
    """Render the detected efforts as compact text rows."""
    if not efforts:
        return [dmc.Text("No best efforts detected yet.", c="dimmed", size="sm")]
    return [dmc.Text(effort_label(effort), size="sm") for effort in efforts]


def note_rows(notes: Sequence[str]) -> list[dmc.Text]:
    """Render prediction notes as compact text rows."""
    return [dmc.Text(note, c="dimmed", size="sm") for note in notes]


def race_predictor_panel() -> dmc.Paper:
    """Build the race predictor form and result card."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Race predictor", fw=600, size="lg"),
                dmc.Text(
                    "Estimates your potential race time from your best efforts. "
                    "Easy runs are weighted through heart rate and efficiency, not "
                    "raw pace.",
                    c="dimmed",
                    size="sm",
                ),
                dmc.Group(
                    [
                        dmc.Select(
                            id="race-distance-preset",
                            label="Race distance",
                            data=distance_options(),
                            value="half",
                            clearable=False,
                            w=200,
                        ),
                        dmc.NumberInput(
                            id="race-distance-custom",
                            label="Custom distance (km)",
                            min=1.0,
                            max=200.0,
                            step=0.1,
                            style={"display": "none"},
                            w=180,
                        ),
                    ],
                    align="flex-end",
                    gap="sm",
                ),
                dmc.Text(
                    "The model is selected automatically (Riegel or critical speed).",
                    c="dimmed",
                    size="xs",
                ),
                dmc.Text("Optional race/time-trial reference", fw=600, size="sm"),
                dmc.Group(
                    [
                        dmc.NumberInput(
                            id="race-reference-distance",
                            label="Reference distance (km)",
                            min=1.0,
                            max=200.0,
                            step=0.1,
                            w=180,
                        ),
                        dmc.NumberInput(
                            id="race-reference-minutes",
                            label="Reference time (min)",
                            min=1.0,
                            step=0.1,
                            w=180,
                        ),
                    ],
                    align="flex-end",
                    gap="sm",
                ),
                dmc.Button("Predict", id="race-predict", variant="filled", w=160),
                dmc.Text(id="race-result-time", fw=700, size="xl"),
                dmc.Text(id="race-result-pace", fw=700, size="lg"),
                dmc.Text(id="race-result-range", c="dimmed", size="sm"),
                dmc.Text(id="race-result-meta", c="dimmed", size="sm"),
                dmc.Stack(id="race-result-notes", gap=2),
                dmc.Text("Detected best efforts", fw=600, size="sm"),
                html.Div(id="race-efforts-list"),
            ],
            gap="sm",
        ),
        p="lg",
        radius="md",
        withBorder=True,
    )
