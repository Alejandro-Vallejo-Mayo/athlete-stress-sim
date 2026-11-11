"""Aerobic decoupling panel and per-kilometre EF chart (``RF-05.3``)."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from athlete_stress_sim.backend.schemas.metrics import DecouplingResponse
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

_EF_COLOR = COLORS["info"]
_NO_DATA_MESSAGE = "No data yet."


def build_decoupling_figure(response: DecouplingResponse) -> go.Figure:
    """Build the per-kilometre efficiency factor bar chart.

    Args:
        response: Aerobic decoupling of one running session.

    Returns:
        A bar chart of ``EF = speed / HR`` per kilometre, or a placeholder when
        there is no data. The decoupling percentage is shown by the panel text.
    """
    if not response.efficiency_per_km:
        return _empty_figure()

    kilometres = list(range(1, len(response.efficiency_per_km) + 1))
    figure = go.Figure(go.Bar(x=kilometres, y=response.efficiency_per_km, marker_color=_EF_COLOR))
    figure.update_layout(xaxis_title="Kilometre", yaxis_title="EF (m/s per bpm)")
    return _style(figure)


def decoupling_status_text(response: DecouplingResponse) -> str:
    """Describe the decoupling percentage in plain language."""
    if response.decoupling_pct is None:
        return "Not enough data to compute decoupling."
    direction = "fell" if response.decoupling_pct > 0 else "rose"
    return f"Decoupling: {response.decoupling_pct:+.1f}% (EF {direction} in the second half)."


def decoupling_panel() -> dmc.Paper:
    """Build the run selector and decoupling chart card."""
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Aerobic decoupling", fw=600, size="lg"),
                dmc.Select(
                    id="decoupling-run",
                    label="Run",
                    placeholder="Select a run",
                    data=[],
                    value=None,
                    w=280,
                ),
                dmc.Text(id="decoupling-status", c="dimmed", size="sm"),
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
        margin={"l": 50, "r": 20, "t": 60, "b": 50},
    )
