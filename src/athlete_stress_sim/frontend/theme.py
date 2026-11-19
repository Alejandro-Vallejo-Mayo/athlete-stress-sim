"""Shared visual tokens, Mantine theme and Plotly styling for the dashboard."""

from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go

FONT_FAMILY = "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"

COLORS: dict[str, str] = {
    "background": "#0B0F14",
    "surface": "#121820",
    "surface_alt": "#18212B",
    "border": "#24303C",
    "text": "#E6EDF3",
    "text_muted": "#93A4B5",
    "primary": "#22B8CF",
    "primary_soft": "rgba(34, 184, 207, 0.14)",
    "ready": "#37B24D",
    "caution": "#F59F00",
    "rest": "#FA5252",
    "fitness": "#5C7CFA",
    "fatigue": "#FF8787",
    "freshness": "#20C997",
    "race": "#FAB005",
    "danger": "#FA5252",
    "warning": "#FAB005",
    "info": "#4DABF7",
}

MANTINE_THEME: dict[str, object] = {
    **dmc.DEFAULT_THEME,
    "primaryColor": "cyan",
    "primaryShade": {"light": 6, "dark": 5},
    "defaultRadius": "md",
    "fontFamily": FONT_FAMILY,
    "headings": {
        **dmc.DEFAULT_THEME["headings"],
        "fontFamily": FONT_FAMILY,
        "fontWeight": "700",
    },
    "respectReducedMotion": True,
}

_SURFACE_STYLE = {
    "backgroundColor": COLORS["surface"],
    "borderColor": COLORS["border"],
    "color": COLORS["text"],
}

_GRID_COLOR = "rgba(255, 255, 255, 0.06)"
_ZERO_LINE_COLOR = "rgba(255, 255, 255, 0.18)"


def surface_style(**overrides: object) -> dict[str, object]:
    """Return the common elevated-surface style, with optional overrides."""
    style: dict[str, object] = dict(_SURFACE_STYLE)
    style.update(overrides)
    return style


def chart_layout(**overrides: object) -> dict[str, object]:
    """Return the shared Plotly layout used by every dashboard chart."""
    layout: dict[str, object] = {
        "template": "plotly_dark",
        "paper_bgcolor": "rgba(0, 0, 0, 0)",
        "plot_bgcolor": "rgba(0, 0, 0, 0)",
        "font": {"family": FONT_FAMILY, "color": COLORS["text_muted"], "size": 12},
        "title": None,
        "margin": {"l": 48, "r": 16, "t": 48, "b": 40},
        "hoverlabel": {
            "bgcolor": COLORS["surface_alt"],
            "bordercolor": COLORS["border"],
            "font": {"color": COLORS["text"]},
        },
        "xaxis": {
            "gridcolor": _GRID_COLOR,
            "zeroline": False,
            "linecolor": COLORS["border"],
            "tickfont": {"color": COLORS["text_muted"]},
        },
        "yaxis": {
            "gridcolor": _GRID_COLOR,
            "zeroline": True,
            "zerolinecolor": _ZERO_LINE_COLOR,
            "tickfont": {"color": COLORS["text_muted"]},
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.0,
            "xanchor": "right",
            "x": 1.0,
            "font": {"color": COLORS["text_muted"]},
        },
    }
    layout.update(overrides)
    return layout


def style_figure(figure: go.Figure, **overrides: object) -> go.Figure:
    """Apply the shared Plotly theme to ``figure`` and return it."""
    figure.update_layout(**chart_layout(**overrides))
    return figure
