"""Fitness-fatigue time-series chart for the dashboard (S12, ``RF-05.1``)."""

from __future__ import annotations

import plotly.graph_objects as go

from athlete_stress_sim.backend.schemas.metrics import BanisterSeriesResponse

_FITNESS_COLOR = "#4c6ef5"
_FATIGUE_COLOR = "#fa5252"
_FRESHNESS_COLOR = "#40c057"
_NO_DATA_MESSAGE = "No data yet."


def build_fitness_figure(series: BanisterSeriesResponse) -> go.Figure:
    """Build the fitness, fatigue and freshness (TSB) time-series chart.

    Args:
        series: Aligned daily fitness-fatigue model output.

    Returns:
        A plotly line chart with one trace per series, or a placeholder when the
        series has no dates.
    """
    if not series.dates:
        return _empty_figure()

    labels = [f"{day:%b} {day.day}" for day in series.dates]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=labels, y=series.fitness, name="Fitness", line={"color": _FITNESS_COLOR})
    )
    figure.add_trace(
        go.Scatter(x=labels, y=series.fatigue, name="Fatigue", line={"color": _FATIGUE_COLOR})
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=series.freshness,
            name="Freshness (TSB)",
            line={"color": _FRESHNESS_COLOR},
        )
    )
    return _style(figure)


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE, showarrow=False, font={"size": 16, "color": "#868e96"}
    )
    return _style(figure)


def _style(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        title="Fitness / Fatigue / Freshness",
        margin={"l": 50, "r": 20, "t": 70, "b": 50},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.0,
            "xanchor": "right",
            "x": 1.0,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure
