"""Fitness-fatigue time-series chart and Trends panel (S12, ``RF-05.1``)."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from athlete_stress_sim.backend.schemas.metrics import BanisterSeriesResponse
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

_FITNESS_COLOR = COLORS["fitness"]
_FATIGUE_COLOR = COLORS["fatigue"]
_FRESHNESS_COLOR = COLORS["freshness"]
_NO_DATA_MESSAGE = "No data yet."


def build_fitness_figure(series: BanisterSeriesResponse) -> go.Figure:
    """Build the fitness, fatigue and freshness (TSB) time-series chart.

    Args:
        series: Aligned daily fitness-fatigue model output.

    Returns:
        A plotly line chart with one trace per series, a range selector and a
        zero line for freshness, or a placeholder when the series has no dates.
    """
    if not series.dates:
        return _empty_figure()

    figure = go.Figure()
    for name, values, color in (
        ("Fitness", series.fitness, _FITNESS_COLOR),
        ("Fatigue", series.fatigue, _FATIGUE_COLOR),
        ("Freshness (TSB)", series.freshness, _FRESHNESS_COLOR),
    ):
        figure.add_trace(
            go.Scatter(
                x=series.dates,
                y=values,
                name=name,
                mode="lines",
                line={"color": color, "width": 2},
                hovertemplate="%{y:.1f}",
            )
        )
    figure.add_hline(y=0.0, line_dash="dot", line_color=COLORS["border"], line_width=1)
    figure = style_figure(
        figure,
        margin={"l": 48, "r": 16, "t": 78, "b": 40},
        hovermode="x unified",
    )
    figure.update_xaxes(
        tickformat="%b %d",
        rangeslider={"visible": False},
        rangeselector={
            "buttons": [
                {"count": 30, "label": "30d", "step": "day", "stepmode": "backward"},
                {"count": 90, "label": "90d", "step": "day", "stepmode": "backward"},
                {"count": 180, "label": "180d", "step": "day", "stepmode": "backward"},
                {"count": 1, "label": "1y", "step": "year", "stepmode": "backward"},
                {"step": "all", "label": "All"},
            ],
            "bgcolor": COLORS["surface_alt"],
            "activecolor": COLORS["primary_soft"],
            "bordercolor": COLORS["border"],
            "font": {"color": COLORS["text_muted"], "size": 11},
            "x": 0.0,
            "y": 1.12,
            "xanchor": "left",
            "yanchor": "top",
        },
    )
    figure.update_yaxes(title_text="Load / freshness (AU)", zeroline=False)
    return figure


def fitness_panel(series: BanisterSeriesResponse) -> dmc.Paper:
    """Build the Trends card with current values and the main chart."""
    if not series.dates:
        content: list[object] = [
            _header(),
            dmc.Text(_NO_DATA_MESSAGE, size="sm", style={"color": COLORS["text_muted"]}),
            dcc.Graph(
                id="fitness-chart",
                figure=_empty_figure(),
                config={"displayModeBar": False, "responsive": True},
                style={"height": "420px"},
            ),
        ]
    else:
        content = [
            _header(series),
            dcc.Graph(
                id="fitness-chart",
                figure=build_fitness_figure(series),
                config={"displayModeBar": False, "responsive": True},
                style={"height": "420px"},
            ),
        ]
    return dmc.Paper(
        dmc.Stack(content, gap="sm"),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def _header(series: BanisterSeriesResponse | None = None) -> dmc.Group:
    left = dmc.Stack(
        [
            dmc.Text("Training load", fw=600, size="lg", style={"color": COLORS["text"]}),
            dmc.Text(
                "Fitness, fatigue and freshness over time. Use the range buttons to zoom.",
                size="sm",
                style={"color": COLORS["text_muted"]},
            ),
        ],
        gap=0,
    )
    if series is None or not series.dates:
        return dmc.Group([left], justify="space-between", align="flex-start", wrap="wrap")

    chips = dmc.Group(
        [
            _chip("Fitness", series.fitness[-1], _FITNESS_COLOR),
            _chip("Fatigue", series.fatigue[-1], _FATIGUE_COLOR),
            _chip("Freshness", series.freshness[-1], _FRESHNESS_COLOR),
        ],
        gap="md",
        wrap="wrap",
    )
    return dmc.Group([left, chips], justify="space-between", align="flex-start", wrap="wrap")


def _chip(label: str, value: float, color: str) -> dmc.Group:
    return dmc.Group(
        [
            dmc.Box(
                w=8,
                h=8,
                style={"borderRadius": "50%", "backgroundColor": color, "flexShrink": 0},
            ),
            dmc.Text(label, size="xs", style={"color": COLORS["text_muted"]}),
            dmc.Text(
                f"{value:.1f}",
                size="sm",
                fw=700,
                style={"color": COLORS["text"], "fontVariantNumeric": "tabular-nums"},
            ),
        ],
        gap=6,
        wrap="nowrap",
    )


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE,
        showarrow=False,
        font={"size": 16, "color": COLORS["text_muted"]},
    )
    return style_figure(figure, margin={"l": 48, "r": 16, "t": 20, "b": 20})
