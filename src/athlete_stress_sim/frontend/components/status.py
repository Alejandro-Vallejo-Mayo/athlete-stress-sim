"""Base dashboard component: daily readiness and freshness panel (S11)."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.frontend.readiness import READINESS_META, Readiness

_NO_DATA_MESSAGE = "No training history yet."
_NEUTRAL_COLOR = "#495057"
_ACCENT_WIDTH = "6px"
_DOT_SIZE = 96


def status_panel(
    readiness: Readiness | None,
    freshness: float | None,
    percentile: float | None = None,
) -> dmc.Paper:
    """Build the daily status card with the readiness traffic light.

    Args:
        readiness: Current readiness level, or ``None`` when there is no history.
        freshness: Current ``fitness - fatigue`` value, or ``None`` when there is no history.
        percentile: Current freshness percentile in the recent history, if available.

    Returns:
        A full-height Mantine ``Paper`` card with a large readiness light on the
        left and the readiness text and freshness metric on the right.
    """
    if readiness is None or freshness is None:
        return _card(_NEUTRAL_COLOR, dmc.Text(_NO_DATA_MESSAGE, c="dimmed"))

    meta = READINESS_META[readiness]
    light = dmc.Box(
        w=_DOT_SIZE,
        h=_DOT_SIZE,
        style={
            "borderRadius": "50%",
            "backgroundColor": meta.color,
            "boxShadow": f"0 0 28px {meta.color}",
            "flexShrink": 0,
        },
    )
    details: list[object] = [
        dmc.Text(meta.label, fw=700, size="xl"),
        dmc.Text(meta.description, c="dimmed", size="sm"),
        dmc.Text(f"Freshness: {freshness:+.1f} AU", fw=700, size="lg"),
    ]
    if percentile is not None:
        details.append(
            dmc.Text(
                f"Percentile of your recent history: P{percentile * 100:.0f}",
                c="dimmed",
                size="sm",
            )
        )
    content = dmc.Group([light, dmc.Stack(details, gap=4)], gap="xl", align="center")
    return _card(meta.color, content)
    content = dmc.Group([light, details], gap="xl", align="center")
    return _card(meta.color, content)


def _card(accent: str, content: dmc.Group | dmc.Text) -> dmc.Paper:
    return dmc.Paper(
        dmc.Stack(
            [dmc.Text("Daily status", fw=600, size="lg"), content],
            gap="lg",
            justify="center",
            h="100%",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style={"height": "100%", "borderLeft": f"{_ACCENT_WIDTH} solid {accent}"},
    )
