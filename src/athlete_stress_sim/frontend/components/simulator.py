"""Tapering simulator panels and forecast chart (S13-S14, ``RF-05.2``)."""

from __future__ import annotations

from datetime import date

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc, html

from athlete_stress_sim.backend.schemas.metrics import PlannedSession, TaperSimulationResponse
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

_FITNESS_COLOR = COLORS["fitness"]
_FATIGUE_COLOR = COLORS["fatigue"]
_FRESHNESS_COLOR = COLORS["freshness"]
_NO_DATA_MESSAGE = "No data yet."
_RACE_COLOR = COLORS["race"]

SessionData = list[dict[str, object]]


def sessions_from_store(data: SessionData) -> list[PlannedSession]:
    """Parse the raw ``dcc.Store`` payload into :class:`PlannedSession` objects.

    Args:
        data: Session dictionaries stored by the dashboard form.

    Returns:
        The planned sessions, skipping malformed entries.
    """
    sessions: list[PlannedSession] = []
    for item in data:
        raw_date = item.get("date")
        if not isinstance(raw_date, str):
            continue
        try:
            sessions.append(
                PlannedSession(
                    date=date.fromisoformat(raw_date),
                    distance_km=_as_float(item["distance_km"]),
                    pace_min_per_km=_as_float(item["pace_min_per_km"]),
                    rpe=_as_float(item["rpe"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sessions


def _as_float(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"Not a numeric value: {value!r}")


def build_taper_figure(
    response: TaperSimulationResponse,
    *,
    race_date: date | None = None,
) -> go.Figure:
    """Build the taper forecast chart splitting history from projection.

    Args:
        response: Combined history + forecast trajectory with the boundary index.
        race_date: Optional race day to highlight with a vertical marker.

    Returns:
        A plotly line chart (history solid, forecast dashed) with a vertical line
        at the history/forecast boundary, or a placeholder when there is no data.
    """
    if not response.dates:
        return _empty_figure()

    split = response.history_end_index
    if split < 0:
        history = slice(0, 0)
        forecast = slice(0, None)
    else:
        history = slice(0, split + 1)
        forecast = slice(split, None)

    labels = [f"{day:%b} {day.day}" for day in response.dates]
    series = [
        ("Fitness", response.fitness, _FITNESS_COLOR),
        ("Fatigue", response.fatigue, _FATIGUE_COLOR),
        ("Freshness (TSB)", response.freshness, _FRESHNESS_COLOR),
    ]
    figure = go.Figure()
    for name, values, color in series:
        figure.add_trace(
            go.Scatter(
                x=labels[history],
                y=values[history],
                name=name,
                line={"color": color},
                mode="lines",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=labels[forecast],
                y=values[forecast],
                name=f"{name} (forecast)",
                line={"color": color, "dash": "dash"},
                mode="lines",
                showlegend=False,
            )
        )

    if 0 <= split < len(labels) - 1:
        figure.add_vline(x=labels[split], line_dash="dot", line_color=COLORS["text_muted"])
    if race_date is not None and race_date in response.dates:
        race_label = labels[response.dates.index(race_date)]
        figure.add_vline(x=race_label, line_dash="dashdot", line_color=_RACE_COLOR)
        figure.add_annotation(
            x=race_label,
            y=1.0,
            yref="paper",
            text="Race day",
            showarrow=False,
            font={"color": _RACE_COLOR},
        )
    return _style(figure, "Taper forecast")


def simulator_panel() -> dmc.Paper:
    """Build the tapering simulator form and forecast chart card."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Tapering simulator", fw=600, size="lg"),
                dmc.Group(
                    [
                        dmc.DateInput(id="sim-date", label="Date", value=None, w=160),
                        dmc.NumberInput(
                            id="sim-distance",
                            label="Distance (km)",
                            min=0.1,
                            step=1.0,
                            value=None,
                            w=150,
                        ),
                        dmc.NumberInput(
                            id="sim-pace",
                            label="Pace (min/km)",
                            min=1.0,
                            step=0.1,
                            value=None,
                            w=150,
                        ),
                        dmc.NumberInput(
                            id="sim-rpe",
                            label="RPE (0-10)",
                            min=0.0,
                            max=10.0,
                            step=0.5,
                            value=None,
                            w=150,
                        ),
                        dmc.Button("Add", id="sim-add", variant="light"),
                        dmc.Button("Clear", id="sim-clear", variant="subtle"),
                    ],
                    align="flex-end",
                    gap="sm",
                    wrap="wrap",
                ),
                dmc.Text(id="sim-form-status", c="red", size="sm"),
                html.Div(id="sim-sessions-list"),
                dmc.Button("Simulate", id="sim-run", variant="filled", w=160),
                dmc.Text(id="sim-run-status", c="dimmed", size="sm"),
                dcc.Graph(
                    id="sim-chart",
                    figure=build_taper_figure(TaperSimulationResponse()),
                    config={"displayModeBar": False, "responsive": True},
                ),
            ],
            gap="md",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def race_taper_panel() -> dmc.Paper:
    """Build the race-aware taper planner form and forecast chart card."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Race taper", fw=600, size="lg"),
                dmc.Text(
                    "Reduce volume over the final weeks while keeping pace and RPE; "
                    "the projection runs up to race morning.",
                    c="dimmed",
                    size="sm",
                ),
                dmc.Group(
                    [
                        dmc.DateInput(
                            id="race-date",
                            label="Race date",
                            value=None,
                            w=160,
                        ),
                        dmc.NumberInput(
                            id="race-base-km",
                            label="Weekly km",
                            min=1.0,
                            step=1.0,
                            value=None,
                            w=140,
                        ),
                        dmc.NumberInput(
                            id="race-runs",
                            label="Runs/week",
                            min=1,
                            max=7,
                            step=1,
                            value=None,
                            w=130,
                        ),
                        dmc.NumberInput(
                            id="race-pace",
                            label="Pace (min/km)",
                            min=1.0,
                            step=0.1,
                            value=None,
                            w=150,
                        ),
                        dmc.NumberInput(
                            id="race-rpe",
                            label="RPE (0-10)",
                            min=0.0,
                            max=10.0,
                            step=0.5,
                            value=None,
                            w=130,
                        ),
                        dmc.NumberInput(
                            id="race-weeks",
                            label="Taper weeks",
                            min=1,
                            max=8,
                            step=1,
                            value=None,
                            w=140,
                        ),
                        dmc.Button("Plan taper", id="race-run", variant="filled"),
                    ],
                    align="flex-end",
                    gap="sm",
                    wrap="wrap",
                ),
                dmc.Text(id="race-plan-status", c="dimmed", size="sm"),
                dcc.Graph(
                    id="race-chart",
                    figure=build_taper_figure(TaperSimulationResponse()),
                    config={"displayModeBar": False, "responsive": True},
                ),
            ],
            gap="md",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def sessions_list(data: SessionData) -> dmc.Stack:
    """Render the planned sessions as a compact readable list."""
    if not data:
        return dmc.Stack(dmc.Text("No planned sessions yet.", c="dimmed", size="sm"), gap=0)
    return dmc.Stack(
        [
            dmc.Text(
                f"{item.get('date')} · {item.get('distance_km')} km @ "
                f"{item.get('pace_min_per_km')} min/km · RPE {item.get('rpe')}",
                size="sm",
            )
            for item in data
        ],
        gap=2,
    )


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE,
        showarrow=False,
        font={"size": 16, "color": COLORS["text_muted"]},
    )
    return _style(figure, "Taper forecast")


def _style(figure: go.Figure, title: str) -> go.Figure:
    return style_figure(
        figure,
        title=title,
        margin={"l": 50, "r": 20, "t": 70, "b": 50},
    )
