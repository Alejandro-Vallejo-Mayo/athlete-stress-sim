"""Plotly Dash application: physiological dashboard and tapering simulator (S13).

Renders the daily readiness panel (S11), the fitness-fatigue time series and the
ACWR risk gauge (S12), and the tapering simulator (S13), all fetched from the
backend metrics API in a dark theme (``RNF-04``).
"""

from __future__ import annotations

from typing import cast

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, ctx, dcc, html

from athlete_stress_sim.backend.schemas.metrics import (
    BanisterSeriesResponse,
    TaperSimulationResponse,
)
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.components.acwr_gauge import build_acwr_gauge
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure
from athlete_stress_sim.frontend.components.simulator import (
    SessionData,
    build_taper_figure,
    sessions_from_store,
    sessions_list,
    simulator_panel,
)
from athlete_stress_sim.frontend.components.status import status_panel
from athlete_stress_sim.frontend.readiness import readiness_level

DashboardOutputs = tuple[object, object, object]
SessionOutputs = tuple[object, object, object, object, object, object, object]


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
                    simulator_panel(),
                    dcc.Store(id="sim-sessions", data=[]),
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

    @app.callback(
        Output("sim-sessions", "data"),
        Output("sim-sessions-list", "children"),
        Output("sim-form-status", "children"),
        Output("sim-date", "value"),
        Output("sim-distance", "value"),
        Output("sim-pace", "value"),
        Output("sim-rpe", "value"),
        Input("sim-add", "n_clicks"),
        Input("sim-clear", "n_clicks"),
        State("sim-sessions", "data"),
        State("sim-date", "value"),
        State("sim-distance", "value"),
        State("sim-pace", "value"),
        State("sim-rpe", "value"),
    )
    def manage_sessions(
        _add: int | None,
        _clear: int | None,
        data: SessionData | None,
        sim_date: str | None,
        distance: float | None,
        pace: float | None,
        rpe: float | None,
    ) -> SessionOutputs:
        """Add or clear planned sessions in the store."""
        sessions = list(data or [])
        if ctx.triggered_id == "sim-clear":
            return ([], sessions_list([]), "", None, None, None, None)
        if ctx.triggered_id == "sim-add":
            if sim_date is None or distance is None or pace is None or rpe is None:
                return (
                    sessions,
                    sessions_list(sessions),
                    "Complete every field before adding.",
                    sim_date,
                    distance,
                    pace,
                    rpe,
                )
            sessions.append(
                {
                    "date": sim_date,
                    "distance_km": float(distance),
                    "pace_min_per_km": float(pace),
                    "rpe": float(rpe),
                }
            )
            return (sessions, sessions_list(sessions), "", None, None, None, None)
        return (sessions, sessions_list(sessions), "", sim_date, distance, pace, rpe)

    @app.callback(
        Output("sim-chart", "figure"),
        Output("sim-run-status", "children"),
        Input("sim-run", "n_clicks"),
        State("sim-sessions", "data"),
        prevent_initial_call=True,
    )
    def run_simulation(_clicks: int | None, data: SessionData | None) -> tuple[object, object]:
        """Project the fitness-fatigue model over the planned sessions."""
        sessions = sessions_from_store(list(data or []))
        if not sessions:
            return (
                cast(object, build_taper_figure(TaperSimulationResponse())),
                "Add a session first.",
            )
        try:
            response = metrics_client.post_taper(sessions)
        except MetricsClientError:
            return (
                cast(object, build_taper_figure(TaperSimulationResponse())),
                "Backend offline.",
            )
        status = f"Projected {len(response.dates)} days."
        return (cast(object, build_taper_figure(response)), status)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, host="0.0.0.0", port=8050)
