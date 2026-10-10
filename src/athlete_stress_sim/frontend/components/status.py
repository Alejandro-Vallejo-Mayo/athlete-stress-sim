"""Base dashboard component: daily readiness and freshness panel (S11)."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.frontend.readiness import READINESS_META, Readiness

_NO_DATA_MESSAGE = "No training history yet."


def status_panel(readiness: Readiness | None, freshness: float | None) -> dmc.Paper:
    """Build the daily status card with the readiness traffic light.

    Args:
        readiness: Current readiness level, or ``None`` when there is no history.
        freshness: Current ``fitness - fatigue`` value, or ``None`` when there is no history.

    Returns:
        A Mantine ``Paper`` card showing the traffic light and the freshness metric.
    """
    if readiness is None or freshness is None:
        return _card(dmc.Text(_NO_DATA_MESSAGE, c="dimmed"))

    meta = READINESS_META[readiness]
    content = dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.ThemeIcon("●", color=meta.color, variant="filled", radius="xl", size="lg"),
                    dmc.Stack(
                        [
                            dmc.Text(meta.label, fw=600),
                            dmc.Text(meta.description, c="dimmed", size="sm"),
                        ],
                        gap=0,
                    ),
                ],
                gap="md",
                align="center",
            ),
            dmc.Text(f"Freshness: {freshness:+.1f} AU", fw=600, size="xl"),
        ],
        gap="md",
    )
    return _card(content)


def _card(content: dmc.Stack | dmc.Text) -> dmc.Paper:
    return dmc.Paper(
        dmc.Stack([dmc.Text("Daily status", fw=600, size="lg"), content], gap="md"),
        p="lg",
        radius="md",
        withBorder=True,
    )
