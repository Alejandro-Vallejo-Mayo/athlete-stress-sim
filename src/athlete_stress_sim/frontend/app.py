"""Plotly Dash application: physiological status panel (S12).

Renders the daily readiness panel (S11), the fitness-fatigue time series and the
ACWR risk gauge fetched from the backend metrics API, in a dark theme
(``RNF-04``). The tapering simulator arrives in S13.
"""

from __future__ import annotations

from typing import cast

import dash
import dash_mantine_components as dmc
from dash import Input, Output, dcc, html

from athlete_stress_sim.backend.schemas.metrics import BanisterSeriesResponse
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.components.acwr_gauge import build_acwr_gauge
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure
from athlete_stress_sim.frontend.components.status import status_panel
from athlete_stress_sim.frontend.readiness import readiness_level

DashboardOutputs = tuple[object, object, object]


def _load_dashboard(client: MetricsClient) -> DashboardOutputs:
    """Fetch both metric series and build the three dashboard panels."""
    series = client.get_banister()
    points = client.get_acwr().points
    if series.freshness:
        freshness = series.freshness[-1]
        panel = status_panel(readiness_level(freshness), freshness)
    else:
        panel = status_panel(None, None)
    return (
        cast(object, panel),
        cast(object, build_fitness_figure(series)),
        cast(object, build_acwr_gauge(points)),
    )


def _empty_dashboard() -> DashboardOutputs:
    """Placeholder panels shown when there is no data or the backend is offline."""
    return (
        cast(object, status_panel(None, None)),
        cast(object, build_fitness_figure(BanisterSeriesResponse())),
        cast(object, build_acwr_gauge([])),
    )


def create_app(client: MetricsClient | None = None) -> dash.Dash:
    """Build and configure the Dash app with a dark, sporty aesthetic."""
    metrics_client = client or MetricsClient()

    app = dash.Dash(__name__)
    app.title = "Athlete Stress Sim"

    initial_fitness = build_fitness_figure(BanisterSeriesResponse())
    initial_gauge = build_acwr_gauge([])

    app.layout = dmc.MantineProvider(
        forceColorScheme="dark",
        children=dmc.Container(
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Title("Athlete Stress Sim", order=1),
                            dmc.Button("Refresh", id="refresh-btn", variant="light"),
                        ],
                        justify="space-between",
                    ),
                    dmc.SimpleGrid(
                        [
                            html.Div(status_panel(None, None), id="status-panel"),
                            dcc.Graph(id="fitness-chart", figure=initial_fitness),
                            dcc.Graph(id="acwr-gauge", figure=initial_gauge),
                        ],
                        cols={"base": 1, "md": 2},
                        spacing="md",
                    ),
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
        Output("fitness-chart", "figure"),
        Output("acwr-gauge", "figure"),
        Input("init", "n_intervals"),
        Input("refresh-btn", "n_clicks"),
    )
    def refresh_dashboard(_interval: int | None, _clicks: int | None) -> DashboardOutputs:
        """Reload the dashboard on first paint and on manual refresh."""
        try:
            return _load_dashboard(metrics_client)
        except MetricsClientError:
            return _empty_dashboard()

    return app


app = create_app()
server = app.server


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, host="0.0.0.0", port=8050)
