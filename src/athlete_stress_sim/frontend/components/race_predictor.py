"""Race time predictor panel (``RF-05.4``)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import dash_mantine_components as dmc
from dash import html

from athlete_stress_sim.backend.schemas.prediction import EffortOut
from athlete_stress_sim.core.metrics.race_prediction import PredictionModel, format_duration
from athlete_stress_sim.frontend.theme import COLORS, surface_style

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


def model_options() -> list[dict[str, str]]:
    """Return the prediction model options, with automatic selection first."""
    return [
        {"value": PredictionModel.AUTO.value, "label": "Auto (recommended)"},
        {"value": PredictionModel.RIEGEL.value, "label": "Riegel"},
        {"value": PredictionModel.CRITICAL_SPEED.value, "label": "Critical speed"},
        {"value": PredictionModel.HR_EXTRAPOLATION.value, "label": "HR extrapolation"},
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
    """Build the race predictor with a result-first layout and advanced inputs."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Stack(
                    [
                        dmc.Text(
                            "Race predictor",
                            fw=600,
                            size="lg",
                            style={"color": COLORS["text"]},
                        ),
                        dmc.Text(
                            "Estimates your potential race time from your best efforts. "
                            "Easy runs are weighted through heart rate and efficiency, not "
                            "raw pace.",
                            size="sm",
                            style={"color": COLORS["text_muted"]},
                        ),
                    ],
                    gap=0,
                ),
                dmc.Text(
                    "Prediction",
                    size="xs",
                    fw=600,
                    tt="uppercase",
                    style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
                ),
                dmc.Group(
                    [
                        dmc.Text(
                            id="race-result-time",
                            fw=700,
                            style={"fontSize": "2rem", "color": COLORS["text"]},
                            children="—",
                        ),
                        dmc.Text(
                            id="race-result-pace",
                            fw=700,
                            size="lg",
                            style={"color": COLORS["text"]},
                            children="—",
                        ),
                    ],
                    gap="xl",
                    align="baseline",
                    wrap="wrap",
                ),
                dmc.Text(
                    id="race-result-range",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                    children="Choose a distance and press Predict.",
                ),
                dmc.Text(id="race-result-meta", size="sm", style={"color": COLORS["text_muted"]}),
                dmc.Stack(id="race-result-notes", gap=2),
                dmc.Text(
                    "Detected best efforts",
                    fw=600,
                    size="sm",
                    style={"color": COLORS["text"]},
                ),
                html.Div(id="race-efforts-list"),
                dmc.Accordion(
                    [
                        dmc.AccordionItem(
                            [
                                dmc.AccordionControl("Prediction inputs"),
                                dmc.AccordionPanel(
                                    dmc.Stack(
                                        [
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
                                                wrap="wrap",
                                            ),
                                            dmc.Text(
                                                "Optional race/time-trial reference",
                                                fw=600,
                                                size="sm",
                                                style={"color": COLORS["text"]},
                                            ),
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
                                                wrap="wrap",
                                            ),
                                            dmc.Button(
                                                "Predict",
                                                id="race-predict",
                                                variant="filled",
                                                w=160,
                                            ),
                                        ],
                                        gap="sm",
                                    )
                                ),
                            ],
                            value="inputs",
                        ),
                        dmc.AccordionItem(
                            [
                                dmc.AccordionControl("Advanced model"),
                                dmc.AccordionPanel(
                                    dmc.Stack(
                                        [
                                            dmc.Select(
                                                id="race-model",
                                                label="Model",
                                                data=model_options(),
                                                value=PredictionModel.AUTO.value,
                                                clearable=False,
                                            ),
                                            dmc.NumberInput(
                                                id="race-exponent",
                                                label="Riegel exponent",
                                                min=0.5,
                                                max=1.5,
                                                step=0.01,
                                                value=1.06,
                                            ),
                                            dmc.Text(
                                                "Auto uses critical speed when possible, then "
                                                "Riegel, then heart-rate extrapolation.",
                                                size="xs",
                                                style={"color": COLORS["text_muted"]},
                                            ),
                                        ],
                                        gap="sm",
                                    )
                                ),
                            ],
                            value="advanced",
                        ),
                    ],
                    value="inputs",
                ),
            ],
            gap="md",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )
