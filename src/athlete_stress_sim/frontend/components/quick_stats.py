"""Compact daily metrics for the Today view."""

from __future__ import annotations

import dash_mantine_components as dmc

from athlete_stress_sim.backend.schemas.metrics import AcwrPoint, BanisterSeriesResponse
from athlete_stress_sim.frontend.components.acwr_gauge import ZONE_META
from athlete_stress_sim.frontend.theme import COLORS, surface_style

_NO_DATA_MESSAGE = "No metrics yet."
_DELTA_WINDOW = 8


def quick_stats_panel(
    series: BanisterSeriesResponse | None,
    points: list[AcwrPoint],
) -> dmc.Paper:
    """Build the at-a-glance card with the four core daily metrics."""
    if series is None or not series.dates:
        return _panel(
            dmc.Stack(
                [
                    _title(),
                    dmc.Text(_NO_DATA_MESSAGE, size="sm", style={"color": COLORS["text_muted"]}),
                ],
                gap="sm",
            )
        )

    zone = ZONE_META[points[-1].zone] if points else None
    stats = [
        _stat(
            "Freshness",
            f"{series.freshness[-1]:+.1f} AU",
            _delta_label(series.freshness),
            COLORS["freshness"],
        ),
        _stat(
            "ACWR",
            f"{points[-1].acwr:.2f}" if points else "—",
            zone.label if zone is not None else "No ratio",
            zone.color if zone is not None else COLORS["text_muted"],
        ),
        _stat(
            "Fitness",
            f"{series.fitness[-1]:.1f}",
            _delta_label(series.fitness),
            COLORS["fitness"],
        ),
        _stat(
            "Fatigue",
            f"{series.fatigue[-1]:.1f}",
            _delta_label(series.fatigue),
            COLORS["fatigue"],
        ),
    ]
    return _panel(
        dmc.Stack(
            [
                _title(),
                dmc.SimpleGrid(stats, cols={"base": 2, "md": 4}, spacing="md"),
            ],
            gap="sm",
        )
    )


def _title() -> dmc.Text:
    return dmc.Text(
        "At a glance",
        size="xs",
        fw=600,
        tt="uppercase",
        style={"color": COLORS["text_muted"], "letterSpacing": "0.08em"},
    )


def _stat(label: str, value: str, detail: str, color: str) -> dmc.Stack:
    return dmc.Stack(
        [
            dmc.Text(label, size="xs", style={"color": COLORS["text_muted"]}),
            dmc.Text(
                value,
                size="xl",
                fw=700,
                style={
                    "color": COLORS["text"],
                    "fontVariantNumeric": "tabular-nums",
                    "lineHeight": "1.1",
                },
            ),
            dmc.Text(detail, size="xs", style={"color": color}),
        ],
        gap=2,
    )


def _delta_label(values: list[float]) -> str:
    if len(values) < _DELTA_WINDOW:
        return "7d —"
    reference = values[-_DELTA_WINDOW]
    return f"7d {values[-1] - reference:+.1f}"


def _panel(content: dmc.Stack) -> dmc.Paper:
    return dmc.Paper(
        content,
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )
