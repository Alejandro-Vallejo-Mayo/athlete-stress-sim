"""Compact freshness (TSB) sparkline for the Today view."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from athlete_stress_sim.backend.schemas.metrics import BanisterSeriesResponse
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

_NO_DATA_MESSAGE = "No freshness history yet."
_GRAPH_STYLE = {"flex": "1 1 0", "minHeight": "180px"}


def build_freshness_figure(series: BanisterSeriesResponse) -> go.Figure:
    """Build the freshness area chart with a zero baseline."""
    if not series.dates:
        return _empty_figure()

    figure = go.Figure(
        go.Scatter(
            x=series.dates,
            y=series.freshness,
            name="Freshness (TSB)",
            mode="lines",
            line={"color": COLORS["freshness"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(32, 201, 151, 0.12)",
        )
    )
    figure.add_hline(y=0.0, line_dash="dot", line_color=COLORS["border"], line_width=1)
    figure = style_figure(
        figure,
        margin={"l": 36, "r": 12, "t": 12, "b": 28},
        showlegend=False,
    )
    figure.update_xaxes(tickformat="%b %d", nticks=5)
    figure.update_yaxes(zeroline=False)
    return figure


def freshness_panel(series: BanisterSeriesResponse) -> dmc.Paper:
    """Build the freshness trend card with a compact chart."""
    if not series.dates:
        content: list[object] = [
            _title(),
            dmc.Text(_NO_DATA_MESSAGE, size="sm", style={"color": COLORS["text_muted"]}),
            dcc.Graph(
                figure=_empty_figure(),
                config={"displayModeBar": False, "responsive": True},
                style=_GRAPH_STYLE,
            ),
        ]
    else:
        content = [
            _title(),
            dmc.Text(
                "Fitness minus fatigue. Above zero means fresher than your recent baseline.",
                size="sm",
                style={"color": COLORS["text_muted"]},
            ),
            dcc.Graph(
                figure=build_freshness_figure(series),
                config={"displayModeBar": False, "responsive": True},
                style=_GRAPH_STYLE,
            ),
        ]
    return dmc.Paper(
        dmc.Stack(content, gap="xs", style={"height": "100%"}),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(height="100%"),
    )


def _title() -> dmc.Text:
    return dmc.Text(
        "Freshness trend",
        size="xs",
        fw=600,
        tt="uppercase",
        style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
    )


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE,
        showarrow=False,
        font={"size": 14, "color": COLORS["text_muted"]},
    )
    figure = style_figure(figure, margin={"l": 8, "r": 8, "t": 12, "b": 8})
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure
