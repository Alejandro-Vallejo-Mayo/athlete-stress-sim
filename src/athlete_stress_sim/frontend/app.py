"""Plotly Dash application: daily status panel (S11).

Renders the readiness traffic light and the current freshness fetched from the
backend metrics API, in a dark theme (``RNF-04``). The fitness-fatigue and ACWR
charts arrive in S12 and the tapering simulator in S13.
"""

from __future__ import annotations

from typing import cast

import dash
import dash_mantine_components as dmc
from dash import Input, Output, dcc, html

from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.components.status import status_panel
from athlete_stress_sim.frontend.readiness import readiness_level


def _load_status(client: MetricsClient) -> object:
    """Fetch the latest freshness and build the corresponding status panel."""
    series = client.get_banister()
    if not series.freshness:
        return cast(object, status_panel(None, None))
    freshness = series.freshness[-1]
    return cast(object, status_panel(readiness_level(freshness), freshness))


def create_app(client: MetricsClient | None = None) -> dash.Dash:
    """Build and configure the Dash app with a dark, sporty aesthetic."""
    metrics_client = client or MetricsClient()

    app = dash.Dash(__name__)
    app.title = "Athlete Stress Sim"

    app.layout = dmc.MantineProvider(
        forceColorScheme="dark",
        children=dmc.Container(
            dmc.Stack(
                [
                    dmc.Title("Athlete Stress Sim", order=1),
                    html.Div(status_panel(None, None), id="status-panel"),
                    dmc.Button("Refresh", id="refresh-btn", variant="light"),
                    dcc.Interval(id="init", interval=1, max_intervals=1),
                ],
                gap="md",
                py="xl",
            ),
            fluid=True,
        ),
    )

    @app.callback(
        Output("status-panel", "children"),
        Input("init", "n_intervals"),
        Input("refresh-btn", "n_clicks"),
    )
    def refresh_status(_interval: int | None, _clicks: int | None) -> object:
        """Reload the status panel on first paint and on manual refresh."""
        try:
            return _load_status(metrics_client)
        except MetricsClientError:
            return cast(object, status_panel(None, None))

    return app


app = create_app()
server = app.server


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, host="0.0.0.0", port=8050)
