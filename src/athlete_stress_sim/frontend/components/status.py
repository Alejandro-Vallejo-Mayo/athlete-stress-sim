"""Daily readiness card for the dashboard (S11, ``RF-05.1``)."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.frontend.readiness import READINESS_META, Readiness
from athlete_stress_sim.frontend.theme import COLORS, surface_style

_NO_DATA_MESSAGE = "No training history yet. Sync Polar to start tracking load and recovery."
_ACCENT_WIDTH = "4px"
_DOT_SIZE = 10


def status_panel(
    readiness: Readiness | None,
    freshness: float | None,
    percentile: float | None = None,
) -> dmc.Paper:
    """Build the daily status card with the readiness verdict and freshness.

    Args:
        readiness: Current readiness level, or ``None`` when there is no history.
        freshness: Current ``fitness - fatigue`` value, or ``None`` when there is no history.
        percentile: Current freshness percentile in the recent history, if available.

    Returns:
        A full-height Mantine ``Paper`` card with the readiness verdict, a short
        recommended action and the freshness metrics.
    """
    if readiness is None or freshness is None:
        content = dmc.Stack(
            [
                _eyebrow("Daily status"),
                dmc.Text(_NO_DATA_MESSAGE, size="sm", style={"color": COLORS["text_muted"]}),
            ],
            gap="sm",
        )
        return _card(COLORS["text_muted"], content)

    meta = READINESS_META[readiness]
    metrics: list[object] = [
        _metric("Freshness", f"{freshness:+.1f} AU"),
    ]
    if percentile is not None:
        metrics.append(_metric("Recent percentile", f"P{percentile * 100:.0f}"))

    content = dmc.Stack(
        [
            dmc.Group(
                [
                    _eyebrow("Daily status"),
                    _status_badge(meta.label, meta.color),
                ],
                justify="space-between",
                gap="sm",
            ),
            dmc.Title(meta.label, order=2, size="h2", style={"color": COLORS["text"]}),
            dmc.Text(
                meta.description,
                size="sm",
                style={"color": COLORS["text_muted"], "maxWidth": "52ch"},
            ),
            dmc.Box(
                dmc.Text(
                    meta.action,
                    size="sm",
                    fw=600,
                    style={"color": COLORS["text"]},
                ),
                style={
                    "backgroundColor": f"{meta.color}14",
                    "borderLeft": f"2px solid {meta.color}",
                    "borderRadius": "6px",
                    "padding": "8px 12px",
                },
            ),
            dmc.Group(metrics, gap="xl", mt="xs"),
        ],
        gap="sm",
    )
    return _card(meta.color, content)


def _eyebrow(text: str) -> dmc.Text:
    return dmc.Text(
        text,
        size="xs",
        fw=600,
        tt="uppercase",
        style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
    )


def _status_badge(label: str, color: str) -> dmc.Badge:
    return dmc.Badge(
        label.upper(),
        variant="light",
        size="sm",
        style={
            "backgroundColor": f"{color}22",
            "border": f"1px solid {color}55",
            "color": color,
        },
    )


def _metric(label: str, value: str) -> dmc.Stack:
    return dmc.Stack(
        [
            dmc.Text(label, size="xs", style={"color": COLORS["text_muted"]}),
            dmc.Text(
                value,
                size="lg",
                fw=700,
                style={"color": COLORS["text"], "fontVariantNumeric": "tabular-nums"},
            ),
        ],
        gap=0,
    )


def _card(accent: str, content: dmc.Stack) -> dmc.Paper:
    return dmc.Paper(
        dmc.Group(
            [
                dmc.Box(
                    w=_DOT_SIZE,
                    h=_DOT_SIZE,
                    style={
                        "borderRadius": "50%",
                        "backgroundColor": accent,
                        "flexShrink": 0,
                        "marginTop": "4px",
                    },
                ),
                dmc.Box(content, style={"flex": "1"}),
            ],
            gap="md",
            align="flex-start",
            wrap="nowrap",
        ),
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(height="100%", borderLeft=f"{_ACCENT_WIDTH} solid {accent}"),
    )
