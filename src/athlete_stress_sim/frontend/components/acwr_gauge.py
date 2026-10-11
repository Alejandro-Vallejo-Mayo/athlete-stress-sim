"""ACWR risk gauge for the dashboard (S12, ``RF-04.2`` and ``RF-05.1``)."""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go

from athlete_stress_sim.backend.schemas.metrics import AcwrPoint
from athlete_stress_sim.core.metrics.acwr import RiskZone

# Risk-zone band boundaries (``RF-04.2``); presentation-local copies of the
# core thresholds (which are private).
UNDERTRAINING_MAX = 0.8
SWEET_SPOT_MAX = 1.3
WARNING_MAX = 1.5
GAUGE_MAX = 2.0
_GAUGE_THICKNESS = 0.5

_NO_DATA_MESSAGE = "No data yet."


@dataclass(frozen=True)
class ZoneMeta:
    """Presentation metadata for an ACWR risk zone."""

    label: str
    color: str


ZONE_META: dict[RiskZone, ZoneMeta] = {
    RiskZone.UNDERTRAINING: ZoneMeta(label="Undertraining", color="#4dabf7"),
    RiskZone.SWEET_SPOT: ZoneMeta(label="Sweet spot", color="#40c057"),
    RiskZone.WARNING: ZoneMeta(label="Warning", color="#fab005"),
    RiskZone.DANGER: ZoneMeta(label="Danger", color="#fa5252"),
}


def build_acwr_gauge(points: list[AcwrPoint]) -> go.Figure:
    """Build the acute:chronic workload ratio gauge with the four colored zones.

    Args:
        points: Daily ACWR series; the last point drives the gauge value.

    Returns:
        A plotly gauge with one colored step per risk zone, or a placeholder when
        ``points`` is empty.
    """
    if not points:
        return _empty_figure()

    latest = points[-1]
    meta = ZONE_META[latest.zone]
    bands = [
        (0.0, UNDERTRAINING_MAX, RiskZone.UNDERTRAINING),
        (UNDERTRAINING_MAX, SWEET_SPOT_MAX, RiskZone.SWEET_SPOT),
        (SWEET_SPOT_MAX, WARNING_MAX, RiskZone.WARNING),
        (WARNING_MAX, GAUGE_MAX, RiskZone.DANGER),
    ]
    # Draw the four risk zones as thick bands and hide the value bar: the fill
    # would otherwise cover the lower zones. The number is tinted with the
    # current zone colour instead.
    steps = [
        {
            "range": [low, high],
            "color": ZONE_META[zone].color,
            "thickness": _GAUGE_THICKNESS,
            "line": {"width": 0},
        }
        for low, high, zone in bands
    ]
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=latest.acwr,
            number={"valueformat": ".2f", "font": {"color": meta.color}},
            title={"text": f"ACWR - {meta.label}"},
            gauge={
                "axis": {"range": [0.0, GAUGE_MAX]},
                "bar": {"color": "rgba(0,0,0,0)"},
                "steps": steps,
            },
        )
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 30, "r": 30, "t": 50, "b": 10},
    )
    return figure


def _empty_figure() -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=_NO_DATA_MESSAGE, showarrow=False, font={"size": 16, "color": "#868e96"}
    )
    figure.update_layout(
        template="plotly_dark",
        title="ACWR",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 30, "r": 30, "t": 50, "b": 10},
    )
    return figure
