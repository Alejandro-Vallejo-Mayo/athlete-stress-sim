"""Plotly Dash application (S1 scaffold).

Only mounts the skeleton with Mantine in dark theme (``RNF-04``). The status,
ACWR and simulator panels are added in S11-S13.
"""

from __future__ import annotations

import dash
import dash_mantine_components as dmc
from dash import html


def create_app() -> dash.Dash:
    """Build and configure the Dash app with a dark, sporty aesthetic."""
    app = dash.Dash(__name__)
    app.title = "Athlete Stress Sim"

    app.layout = dmc.MantineProvider(
        forceColorScheme="dark",
        children=dmc.Container(
            dmc.Stack(
                [
                    dmc.Title("Athlete Stress Sim", order=1),
                    dmc.Text(
                        "Dashboard scaffold. Panels available in S11-S13.",
                        c="dimmed",
                    ),
                    html.Div(id="status-panel"),
                ],
                gap="md",
                py="xl",
            ),
            fluid=True,
        ),
    )
    return app


app = create_app()
server = app.server


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, host="0.0.0.0", port=8050)
