"""Aerobic decoupling panel, summary and per-kilometre EF chart (``RF-05.3``)."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc, html

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut
from athlete_stress_sim.backend.schemas.metrics import DecouplingResponse
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

_EF_COLOR = COLORS["info"]
_NO_DATA_MESSAGE = "No data yet."
_CONTEXT = "EF is speed / HR. A drop above 5% suggests aerobic drift in the second half."
_GOOD_DECOUPLING_MAX = 5.0
_CAUTION_DECOUPLING_MAX = 10.0


def build_decoupling_figure(response: DecouplingResponse) -> go.Figure:
    """Build the per-kilometre efficiency factor bar chart.

    Args:
        response: Aerobic decoupling of one running session.

    Returns:
        A bar chart of ``EF = speed / HR`` per kilometre with a mean reference
        line, or a placeholder when there is no data.
    """
    if not response.efficiency_per_km:
        return _empty_figure()

    kilometres = list(range(1, len(response.efficiency_per_km) + 1))
    figure = go.Figure(
        go.Bar(
            x=kilometres,
            y=response.efficiency_per_km,
            marker_color=_EF_COLOR,
            hovertemplate="km %{x}: %{y:.3f}<extra></extra>",
        )
    )
    mean_ef = sum(response.efficiency_per_km) / len(response.efficiency_per_km)
    figure.add_hline(
        y=mean_ef,
        line_dash="dot",
        line_color=COLORS["text_muted"],
        line_width=1,
        annotation_text=f"Mean {mean_ef:.3f}",
        annotation_position="top left",
        annotation_font={"color": COLORS["text_muted"], "size": 10},
    )
    figure.update_layout(xaxis_title="Kilometre", yaxis_title="EF (m/s per bpm)")
    return _style(figure)


def decoupling_status_text(response: DecouplingResponse) -> str:
    """Describe the decoupling percentage in plain language."""
    if response.decoupling_pct is None:
        return "Not enough data to compute decoupling."
    direction = "fell" if response.decoupling_pct > 0 else "rose"
    return f"Decoupling: {response.decoupling_pct:+.1f}% (EF {direction} in the second half)."


def decoupling_summary(
    response: DecouplingResponse | None,
    exercise: ExerciseOut | None = None,
) -> dmc.Stack:
    """Build the session summary shown above the decoupling chart."""
    if response is None or response.decoupling_pct is None:
        return dmc.Stack(
            [
                dmc.Text(
                    "Select a run to inspect its aerobic decoupling.",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
                dmc.Text(_CONTEXT, size="xs", style={"color": COLORS["text_muted"]}),
            ],
            gap="xs",
        )

    color = _decoupling_color(response.decoupling_pct)
    details: list[str] = []
    if exercise is not None:
        if exercise.start_time is not None:
            details.append(exercise.start_time.strftime("%b %d"))
        if exercise.distance_m:
            details.append(f"{exercise.distance_m / 1000.0:.1f} km")
        if exercise.duration_s:
            details.append(f"{exercise.duration_s / 60.0:.0f} min")
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Badge(
                        f"{response.decoupling_pct:+.1f}%",
                        style={
                            "backgroundColor": f"{color}22",
                            "border": f"1px solid {color}55",
                            "color": color,
                        },
                    ),
                    dmc.Text(
                        " · ".join(details) if details else "Run summary unavailable.",
                        size="sm",
                        style={"color": COLORS["text"]},
                    ),
                ],
                gap="sm",
                wrap="wrap",
            ),
            dmc.Text(
                decoupling_status_text(response),
                size="sm",
                style={"color": COLORS["text_muted"]},
            ),
            dmc.Text(_CONTEXT, size="xs", style={"color": COLORS["text_muted"]}),
        ],
        gap="xs",
    )


def decoupling_panel() -> dmc.Paper:
    """Build the run selector, session summary and decoupling chart card."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Aerobic decoupling", fw=600, size="lg", style={"color": COLORS["text"]}),
                dmc.Text(
                    "Compare the first and second half of a run at the same heart rate.",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
                dmc.Select(
                    id="decoupling-run",
                    label="Run",
                    placeholder="Select a run",
                    data=[],
                    value=None,
                    w=280,
                ),
                html.Div(decoupling_summary(None), id="decoupling-summary"),
                dcc.Graph(
                    id="decoupling-chart",
                    figure=build_decoupling_figure(DecouplingResponse(exercise_id="")),
                    config={"displayModeBar": False, "responsive": True},
                    style={"height": "340px"},
                ),
            ],
            gap="md",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def _decoupling_color(value: float) -> str:
    if value <= _GOOD_DECOUPLING_MAX:
        return COLORS["ready"]
    if value <= _CAUTION_DECOUPLING_MAX:
        return COLORS["caution"]
    return COLORS["rest"]


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE,
        showarrow=False,
        font={"size": 16, "color": COLORS["text_muted"]},
    )
    return _style(figure)


def _style(figure: go.Figure) -> go.Figure:
    return style_figure(
        figure,
        title="Efficiency factor per kilometre",
        margin={"l": 50, "r": 20, "t": 50, "b": 50},
    )
