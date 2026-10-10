"""Aerobic decoupling panel and per-kilometre EF chart (``RF-05.3``)."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from athlete_stress_sim.backend.schemas.metrics import DecouplingResponse

_EF_COLOR = "#4dabf7"
_NO_DATA_MESSAGE = "No data yet."


def build_decoupling_figure(response: DecouplingResponse) -> go.Figure:
    """Build the per-kilometre efficiency factor bar chart.

    Args:
        response: Aerobic decoupling of one running session.

    Returns:
        A bar chart of ``EF = speed / HR`` per kilometre, annotated with the
        decoupling percentage, or a placeholder when there is no data.
    """
    if not response.efficiency_per_km:
        return _empty_figure()

    kilometres = list(range(1, len(response.efficiency_per_km) + 1))
    figure = go.Figure(go.Bar(x=kilometres, y=response.efficiency_per_km, marker_color=_EF_COLOR))
    figure.update_layout(xaxis_title="Kilometre", yaxis_title="EF (m/s per bpm)")
    if response.decoupling_pct is not None:
        figure.add_annotation(
            text=decoupling_status_text(response),
            xref="paper",
            yref="paper",
            x=0.0,
            y=1.15,
            showarrow=False,
            font={"size": 13},
        )
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
                ),
            ],
            gap="md",
        ),
        p="lg",
        radius="md",
        withBorder=True,
    )


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE, showarrow=False, font={"size": 16, "color": "#868e96"}
    )
    return _style(figure)


def _style(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        title="Efficiency factor per kilometre",
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure
