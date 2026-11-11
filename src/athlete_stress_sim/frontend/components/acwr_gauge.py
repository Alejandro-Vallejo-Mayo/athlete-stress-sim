"""ACWR risk strip and summary panel (S12, ``RF-04.2`` and ``RF-05.1``)."""

from __future__ import annotations

from dataclasses import dataclass

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from athlete_stress_sim.backend.schemas.metrics import AcwrPoint
from athlete_stress_sim.core.metrics.acwr import RiskZone
from athlete_stress_sim.frontend.theme import COLORS, style_figure, surface_style

# Risk-zone band boundaries (``RF-04.2``); presentation-local copies of the
# core thresholds (which are private).
UNDERTRAINING_MAX = 0.8
SWEET_SPOT_MAX = 1.3
WARNING_MAX = 1.5
GAUGE_MAX = 2.0

_NO_DATA_MESSAGE = "No data yet."


@dataclass(frozen=True)
class ZoneMeta:
    """Presentation metadata for an ACWR risk zone."""

    label: str
    color: str


ZONE_META: dict[RiskZone, ZoneMeta] = {
    RiskZone.UNDERTRAINING: ZoneMeta(label="Undertraining", color=COLORS["info"]),
    RiskZone.SWEET_SPOT: ZoneMeta(label="Sweet spot", color=COLORS["ready"]),
    RiskZone.WARNING: ZoneMeta(label="Warning", color=COLORS["warning"]),
    RiskZone.DANGER: ZoneMeta(label="Danger", color=COLORS["danger"]),
}


def build_acwr_risk_figure(points: list[AcwrPoint]) -> go.Figure:
    """Build the horizontal ACWR risk strip.

    Args:
        points: Daily ACWR series; the last point drives the marker.

    Returns:
        A compact risk strip with four colored zones and a marker for the latest
        ratio, or a placeholder when ``points`` is empty.
    """
    if not points:
        return _empty_figure()

    latest = points[-1]
    meta = ZONE_META[latest.zone]
    upper = max(GAUGE_MAX, latest.acwr + 0.2)
    bands = [
        (0.0, UNDERTRAINING_MAX, RiskZone.UNDERTRAINING),
        (UNDERTRAINING_MAX, SWEET_SPOT_MAX, RiskZone.SWEET_SPOT),
        (SWEET_SPOT_MAX, WARNING_MAX, RiskZone.WARNING),
        (WARNING_MAX, GAUGE_MAX, RiskZone.DANGER),
    ]
    figure = go.Figure()
    for low, high, zone in bands:
        figure.add_shape(
            type="rect",
            x0=low,
            x1=high,
            y0=0.0,
            y1=1.0,
            line={"width": 0},
            fillcolor=ZONE_META[zone].color,
            opacity=0.28,
            layer="below",
        )
        figure.add_annotation(
            x=(low + high) / 2.0,
            y=0.5,
            text=ZONE_META[zone].label,
            showarrow=False,
            font={"size": 10, "color": COLORS["text_muted"]},
        )
    figure.add_shape(
        type="line",
        x0=latest.acwr,
        x1=latest.acwr,
        y0=-0.08,
        y1=1.08,
        line={"color": COLORS["text"], "width": 2},
    )
    figure.add_annotation(
        x=latest.acwr,
        y=1.22,
        text=f"{latest.acwr:.2f}",
        showarrow=False,
        font={"size": 16, "color": meta.color},
        xanchor="center",
    )
    figure = style_figure(
        figure,
        margin={"l": 8, "r": 8, "t": 34, "b": 8},
        showlegend=False,
    )
    figure.update_xaxes(range=[0.0, upper], visible=False, fixedrange=True)
    figure.update_yaxes(range=[-0.15, 1.35], visible=False, fixedrange=True)
    return figure


def acwr_risk_panel(points: list[AcwrPoint]) -> dmc.Paper:
    """Build the load-risk card with the ACWR strip and its components."""
    if not points:
        return _panel(
            [
                _header("Load risk", None),
                _graph([]),
                dmc.Text(
                    "Sync training history to compute the acute:chronic ratio.",
                    size="sm",
                    style={"color": COLORS["text_muted"]},
                ),
            ]
        )

    latest = points[-1]
    meta = ZONE_META[latest.zone]
    return _panel(
        [
            _header("Load risk", meta),
            _graph(points),
            dmc.Group(
                [
                    _stat("Acute 7d", f"{latest.acute:.1f}"),
                    _stat("Chronic 28d", f"{latest.chronic:.1f}"),
                    _stat("Ratio", f"{latest.acwr:.2f}"),
                ],
                gap="xl",
                mt="xs",
            ),
        ]
    )


def _graph(points: list[AcwrPoint]) -> dcc.Graph:
    return dcc.Graph(
        figure=build_acwr_risk_figure(points),
        config={"displayModeBar": False},
        style={"height": "150px"},
    )


def _header(title: str, meta: ZoneMeta | None) -> dmc.Group:
    children: list[object] = [dmc.Text(title, fw=600, size="lg", style={"color": COLORS["text"]})]
    if meta is not None:
        children.append(
            dmc.Badge(
                meta.label.upper(),
                variant="light",
                size="sm",
                style={
                    "backgroundColor": f"{meta.color}22",
                    "border": f"1px solid {meta.color}55",
                    "color": meta.color,
                },
            )
        )
    return dmc.Group(children, justify="space-between", gap="sm")


def _stat(label: str, value: str) -> dmc.Stack:
    return dmc.Stack(
        [
            dmc.Text(label, size="xs", style={"color": COLORS["text_muted"]}),
            dmc.Text(
                value,
                size="md",
                fw=700,
                style={"color": COLORS["text"], "fontVariantNumeric": "tabular-nums"},
            ),
        ],
        gap=0,
    )


def _panel(children: list[object]) -> dmc.Paper:
    return dmc.Paper(
        dmc.Stack(children, gap="sm"),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(height="100%"),
    )


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE,
        showarrow=False,
        font={"size": 16, "color": COLORS["text_muted"]},
    )
    figure = style_figure(figure, margin={"l": 8, "r": 8, "t": 20, "b": 8})
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure
