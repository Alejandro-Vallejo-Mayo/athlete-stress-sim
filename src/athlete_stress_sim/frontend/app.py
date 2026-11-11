"""Plotly Dash application: physiological dashboard, simulator and decoupling.

Renders the daily readiness panel (S11), the fitness-fatigue time series and the
ACWR risk gauge (S12), the tapering simulator (S13), the race-aware taper planner
(S14) and the aerobic-decoupling panel (``RF-05.3``), all fetched from the
backend metrics API in a dark theme (``RNF-04``).
"""

from __future__ import annotations

import os
from datetime import date
from typing import cast

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, ctx, dcc, html

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut
from athlete_stress_sim.backend.schemas.metrics import (
    BanisterSeriesResponse,
    CalibrationResponse,
    DecouplingResponse,
    TaperPlanRequest,
    TaperSimulationResponse,
)
from athlete_stress_sim.backend.schemas.prediction import (
    RacePredictionRequest,
    RaceReference,
)
from athlete_stress_sim.core.metrics.race_prediction import PredictionModel, format_duration
from athlete_stress_sim.frontend.api import MetricsClient, MetricsClientError
from athlete_stress_sim.frontend.components.acwr_gauge import acwr_risk_panel
from athlete_stress_sim.frontend.components.decoupling import (
    build_decoupling_figure,
    decoupling_panel,
    decoupling_status_text,
)
from athlete_stress_sim.frontend.components.fitness_chart import build_fitness_figure
from athlete_stress_sim.frontend.components.freshness_chart import freshness_panel
from athlete_stress_sim.frontend.components.quick_stats import quick_stats_panel
from athlete_stress_sim.frontend.components.race_predictor import (
    effort_rows,
    format_pace,
    note_rows,
    optional_float,
    preset_distance,
    race_predictor_panel,
)
from athlete_stress_sim.frontend.components.rpe import (
    pending_gym_sessions,
    rpe_modal,
    rpe_pending_card,
    rpe_pending_children,
    rpe_pending_message,
    rpe_pending_style,
    rpe_session_options,
)
from athlete_stress_sim.frontend.components.simulator import (
    SessionData,
    build_taper_figure,
    race_taper_panel,
    sessions_from_store,
    sessions_list,
    simulator_panel,
)
from athlete_stress_sim.frontend.components.status import status_panel
from athlete_stress_sim.frontend.readiness import assess_readiness
from athlete_stress_sim.frontend.theme import COLORS, MANTINE_THEME, surface_style

DashboardOutputs = tuple[
    object,
    object,
    object,
    object,
    object,
    list[dict[str, str]],
    str | None,
    object | None,
]
RefreshOutputs = tuple[
    object,
    object,
    object,
    object,
    object,
    list[dict[str, str]],
    str | None,
    int,
    str,
    object | None,
]
SessionOutputs = tuple[object, object, object, object, object, object, object]
_MAX_RPE = 10.0


def _run_option(exercise: ExerciseOut) -> dict[str, str]:
    """Build one selectable option for the decoupling run selector."""
    when = exercise.start_time.date().isoformat() if exercise.start_time else "unknown"
    distance = f"{exercise.distance_m / 1000.0:.1f} km" if exercise.distance_m else "no distance"
    return {"value": exercise.exercise_id, "label": f"{when} · {distance}"}


def _model_label(calibration: CalibrationResponse) -> str:
    """Describe whether the projection uses calibrated parameters or priors."""
    if calibration.calibrated:
        if calibration.cv_improvement is not None:
            return f"calibrated (CV +{calibration.cv_improvement:.0%})"
        if calibration.r_squared is not None:
            return f"calibrated (R²={calibration.r_squared:.2f})"
    return "priors (calibration not reliable)"


def _no_data_alert() -> dmc.Alert:
    """Explain how to populate an empty dashboard."""
    return dmc.Alert(
        "No training history yet. Sync Polar to populate load, recovery and risk.",
        title="No data",
        color="blue",
        variant="light",
    )


def _offline_alert() -> dmc.Alert:
    """Explain that the backend could not be reached."""
    return dmc.Alert(
        "The metrics API is unreachable. Start the backend and press Refresh.",
        title="Backend offline",
        color="red",
        variant="light",
    )


def _sync_error_alert() -> dmc.Alert:
    """Explain that the manual Polar sync failed."""
    return dmc.Alert(
        "Sync failed. Check the Polar connection and retry.",
        title="Sync error",
        color="orange",
        variant="light",
    )


def _load_dashboard(client: MetricsClient, current_run: str | None) -> DashboardOutputs:
    """Fetch the metric series and the run list, keeping the current selection."""
    series = client.get_banister()
    points = client.get_acwr().points
    options = [_run_option(exercise) for exercise in client.get_exercises("run")]
    if series.freshness:
        freshness = series.freshness[-1]
        readiness, percentile = assess_readiness(freshness, series.freshness)
        panel = status_panel(readiness, freshness, percentile)
    else:
        panel = status_panel(None, None)
    valid = {option["value"] for option in options}
    selected = current_run if current_run in valid else (options[0]["value"] if options else None)
    alert = _no_data_alert() if not series.dates and not points else None
    return (
        cast(object, panel),
        cast(object, build_fitness_figure(series)),
        cast(object, acwr_risk_panel(points)),
        cast(object, freshness_panel(series)),
        cast(object, quick_stats_panel(series, points)),
        options,
        selected,
        alert,
    )


def _empty_dashboard() -> DashboardOutputs:
    """Placeholder panels shown when the backend is offline."""
    return (
        cast(object, status_panel(None, None)),
        cast(object, build_fitness_figure(BanisterSeriesResponse())),
        cast(object, acwr_risk_panel([])),
        cast(object, freshness_panel(BanisterSeriesResponse())),
        cast(object, quick_stats_panel(None, [])),
        [],
        None,
        _offline_alert(),
    )


def _card(content: object) -> dmc.Paper:
    """Wrap a panel or chart in the shared elevated surface."""
    return dmc.Paper(
        content,
        p="lg",
        radius="md",
        withBorder=True,
        style=surface_style(),
    )


def _header() -> dmc.AppShellHeader:
    """Build the fixed application header with sync and RPE actions."""
    return dmc.AppShellHeader(
        dmc.Group(
            [
                dmc.Stack(
                    [
                        dmc.Title(
                            "Athlete Stress Sim",
                            order=1,
                            size="h3",
                            style={"color": COLORS["text"]},
                        ),
                        dmc.Text(
                            "Training load and injury risk",
                            size="xs",
                            visibleFrom="sm",
                            style={"color": COLORS["text_muted"]},
                        ),
                    ],
                    gap=0,
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            id="rpe-pending-btn",
                            variant="light",
                            color="orange",
                            size="xs",
                            style={"display": "none"},
                            children="RPE pending",
                        ),
                        dmc.Text(
                            id="sync-status",
                            size="xs",
                            style={"color": COLORS["text_muted"]},
                        ),
                        dmc.Button("Refresh", id="refresh-btn", variant="light", size="xs"),
                    ],
                    gap="sm",
                    align="center",
                    wrap="wrap",
                    justify="flex-end",
                ),
            ],
            justify="space-between",
            align="center",
            h="100%",
            px="md",
        ),
        style={
            "backgroundColor": COLORS["surface"],
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def _today_tab() -> dmc.Stack:
    """Build the today overview: readiness, load risk and freshness."""
    return dmc.Stack(
        [
            html.Div(id="dashboard-alert"),
            dmc.SimpleGrid(
                [
                    html.Div(
                        status_panel(None, None),
                        id="status-panel",
                        style={"height": "100%"},
                    ),
                    html.Div(
                        acwr_risk_panel([]),
                        id="acwr-risk-panel",
                        style={"height": "100%"},
                    ),
                ],
                cols={"base": 1, "lg": 2},
                spacing="md",
                style={"alignItems": "stretch"},
            ),
            html.Div(quick_stats_panel(None, []), id="quick-stats"),
            dmc.SimpleGrid(
                [
                    html.Div(
                        freshness_panel(BanisterSeriesResponse()),
                        id="freshness-panel",
                    ),
                    rpe_pending_card(),
                ],
                cols={"base": 1, "lg": 2},
                spacing="md",
                style={"alignItems": "stretch"},
            ),
        ],
        gap="lg",
    )


def _trends_tab(initial_fitness: object) -> dmc.Stack:
    """Build the historical view: fitness-fatigue and decoupling."""
    return dmc.Stack(
        [
            _card(
                dcc.Graph(
                    id="fitness-chart",
                    figure=initial_fitness,
                    config={"displayModeBar": False, "responsive": True},
                    style={"height": "420px"},
                )
            ),
            decoupling_panel(),
        ],
        gap="lg",
    )


def _plan_tab() -> dmc.Stack:
    """Build the planning tools: taper, simulator and race prediction."""
    return dmc.Stack(
        [
            simulator_panel(),
            race_taper_panel(),
            race_predictor_panel(),
        ],
        gap="lg",
    )


def create_app(client: MetricsClient | None = None) -> dash.Dash:
    """Build and configure the Dash app with a dark, performance-lab aesthetic."""
    metrics_client = client or MetricsClient()

    app = dash.Dash(__name__)
    app.title = "Athlete Stress Sim"

    initial_fitness = build_fitness_figure(BanisterSeriesResponse())

    app.layout = dmc.MantineProvider(
        forceColorScheme="dark",
        theme=MANTINE_THEME,
        children=dmc.AppShell(
            header={"height": 68},
            padding="md",
            children=[
                _header(),
                dmc.AppShellMain(
                    dmc.Container(
                        [
                            dcc.Loading(
                                type="circle",
                                color=COLORS["primary"],
                                children=dmc.Tabs(
                                    value="today",
                                    keepMounted=True,
                                    variant="pills",
                                    children=[
                                        dmc.TabsList(
                                            [
                                                dmc.TabsTab("Today", value="today"),
                                                dmc.TabsTab("Trends", value="trends"),
                                                dmc.TabsTab("Plan", value="plan"),
                                            ],
                                            justify="left",
                                        ),
                                        dmc.TabsPanel(
                                            _today_tab(),
                                            value="today",
                                            pt="md",
                                        ),
                                        dmc.TabsPanel(
                                            _trends_tab(initial_fitness),
                                            value="trends",
                                            pt="md",
                                        ),
                                        dmc.TabsPanel(_plan_tab(), value="plan", pt="md"),
                                    ],
                                ),
                            ),
                            rpe_modal(),
                            dcc.Store(id="sim-sessions", data=[]),
                            dcc.Store(id="data-refreshed", data=0),
                            dcc.Store(id="rpe-refresh", data=0),
                            dcc.Store(id="metric-refresh", data=0),
                            dcc.Interval(id="init", interval=1, max_intervals=1),
                        ],
                        fluid=True,
                        py="lg",
                        mx="auto",
                        style={"maxWidth": "1440px"},
                    ),
                    style={"backgroundColor": COLORS["background"], "minHeight": "100vh"},
                ),
            ],
        ),
    )

    @app.callback(
        Output("status-panel", "children"),
        Output("fitness-chart", "figure"),
        Output("acwr-risk-panel", "children"),
        Output("freshness-panel", "children"),
        Output("quick-stats", "children"),
        Output("decoupling-run", "data"),
        Output("decoupling-run", "value"),
        Output("data-refreshed", "data"),
        Output("sync-status", "children"),
        Output("dashboard-alert", "children"),
        Input("init", "n_intervals"),
        Input("refresh-btn", "n_clicks"),
        Input("metric-refresh", "data"),
        State("decoupling-run", "value"),
        State("data-refreshed", "data"),
    )
    def refresh_dashboard(
        _interval: int | None,
        _clicks: int | None,
        _metrics: int | None,
        current_run: str | None,
        refreshed: int | None,
    ) -> RefreshOutputs:
        """Sync on manual refresh, then reload the dashboard panels."""
        sync_text = ""
        if ctx.triggered_id == "refresh-btn":
            try:
                result = metrics_client.sync()
                sync_text = f"Synced +{result.sync.downloaded} · parsed {result.parse.parsed}"
            except MetricsClientError:
                sync_text = "Sync failed."
        try:
            status, fitness, acwr, freshness, quick, options, selected, alert = _load_dashboard(
                metrics_client, current_run
            )
        except MetricsClientError:
            status, fitness, acwr, freshness, quick, options, selected, alert = _empty_dashboard()
        if sync_text == "Sync failed.":
            alert = _sync_error_alert()
        return (
            status,
            fitness,
            acwr,
            freshness,
            quick,
            options,
            selected,
            int(refreshed or 0) + 1,
            sync_text,
            alert,
        )

    @app.callback(
        Output("decoupling-chart", "figure"),
        Output("decoupling-status", "children"),
        Input("decoupling-run", "value"),
    )
    def render_decoupling(exercise_id: str | None) -> tuple[object, object]:
        """Render the per-kilometre efficiency of the selected run."""
        if exercise_id is None:
            return (
                cast(object, build_decoupling_figure(DecouplingResponse(exercise_id=""))),
                "No runs available.",
            )
        try:
            response = metrics_client.get_decoupling(exercise_id)
        except MetricsClientError:
            return (
                cast(object, build_decoupling_figure(DecouplingResponse(exercise_id=exercise_id))),
                "Backend offline.",
            )
        return (
            cast(object, build_decoupling_figure(response)),
            decoupling_status_text(response),
        )

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
            calibration = metrics_client.get_calibration()
            response = metrics_client.post_taper(sessions, calibration.params)
        except MetricsClientError:
            return (
                cast(object, build_taper_figure(TaperSimulationResponse())),
                "Backend offline.",
            )
        status = f"Projected {len(response.dates)} days · model: {_model_label(calibration)}."
        return (cast(object, build_taper_figure(response)), status)

    _register_rpe_callbacks(app, metrics_client)
    _register_race_taper_callbacks(app, metrics_client)
    _register_race_predictor_callbacks(app, metrics_client)
    return app


def _register_race_predictor_callbacks(app: dash.Dash, client: MetricsClient) -> None:
    """Register the race predictor form and best-effort list callbacks."""

    @app.callback(
        Output("race-distance-custom", "style"),
        Input("race-distance-preset", "value"),
    )
    def toggle_custom_distance(preset: str | None) -> dict[str, str]:
        """Show the custom distance field only when the custom preset is selected."""
        return {"display": "block"} if preset == "custom" else {"display": "none"}

    @app.callback(
        Output("race-efforts-list", "children"),
        Input("data-refreshed", "data"),
    )
    def load_best_efforts(_refreshed: int | None) -> list[object]:
        """Show the best efforts detected in the persisted history."""
        try:
            efforts = client.get_best_efforts()
        except MetricsClientError:
            return [dmc.Text("Backend offline.", c="red", size="sm")]
        return list(effort_rows(efforts))

    @app.callback(
        Output("race-result-time", "children"),
        Output("race-result-pace", "children"),
        Output("race-result-range", "children"),
        Output("race-result-meta", "children"),
        Output("race-result-notes", "children"),
        Output("race-efforts-list", "children", allow_duplicate=True),
        Input("race-predict", "n_clicks"),
        State("race-distance-preset", "value"),
        State("race-distance-custom", "value"),
        State("race-reference-distance", "value"),
        State("race-reference-minutes", "value"),
        prevent_initial_call=True,
    )
    def run_race_prediction(  # noqa: PLR0917
        _clicks: int | None,
        preset: str | None,
        custom_distance_km: object,
        reference_distance_km: object,
        reference_minutes: object,
    ) -> tuple[object, object, object, object, list[object], list[object]]:
        """Predict the race time and render the result and the efforts used."""
        target_distance = (
            optional_float(custom_distance_km) if preset == "custom" else preset_distance(preset)
        )
        if target_distance is None or target_distance <= 0.0:
            return ("—", "—", "", "Enter a target distance.", [], [])
        reference_km = optional_float(reference_distance_km)
        reference_min = optional_float(reference_minutes)
        if (reference_km is None) != (reference_min is None):
            return (
                "—",
                "—",
                "",
                "Provide both reference distance and time, or neither.",
                [],
                [],
            )
        reference = None
        if reference_km is not None and reference_min is not None:
            reference = RaceReference(
                distance_km=reference_km,
                time_s=reference_min * 60.0,
            )
        try:
            prediction = client.predict_race(
                RacePredictionRequest(
                    distance_km=target_distance,
                    model=PredictionModel.AUTO,
                    reference=reference,
                )
            )
        except (MetricsClientError, ValueError):
            return ("—", "—", "", "Backend offline or invalid input.", [], [])
        predicted_time = prediction.predicted_time_s
        if predicted_time is None:
            return (
                "—",
                "—",
                "",
                f"{prediction.model.value} · {prediction.confidence.value} confidence",
                list(note_rows(prediction.notes)),
                list(effort_rows(prediction.efforts)),
            )
        time_text = format_duration(predicted_time)
        pace_text = format_pace(prediction.predicted_pace_s_per_km)
        fast = "—" if prediction.fast_time_s is None else format_duration(prediction.fast_time_s)
        slow = "—" if prediction.slow_time_s is None else format_duration(prediction.slow_time_s)
        range_text = f"Range: {fast} – {slow}"
        meta = f"{prediction.model.value} · {prediction.confidence.value} confidence"
        return (
            time_text,
            pace_text,
            range_text,
            meta,
            list(note_rows(prediction.notes)),
            list(effort_rows(prediction.efforts)),
        )


def _register_rpe_callbacks(app: dash.Dash, client: MetricsClient) -> None:
    """Register the pending-RPE badge and the modal that records the RPE."""

    @app.callback(
        Output("rpe-pending-btn", "style"),
        Output("rpe-pending-btn", "children"),
        Output("rpe-pending-text", "children"),
        Output("rpe-card-open", "style"),
        Output("rpe-session-select", "data"),
        Output("rpe-session-select", "value"),
        Input("data-refreshed", "data"),
        Input("rpe-refresh", "data"),
    )
    def load_pending_rpe(
        _refreshed: int | None,
        _saved: int | None,
    ) -> tuple[dict[str, str], object, str, dict[str, str], list[dict[str, str]], str | None]:
        """Show how many gym sessions are still missing an RPE."""
        try:
            exercises = client.get_exercises("gym")
        except MetricsClientError:
            return (
                rpe_pending_style(0),
                "RPE pending",
                "RPE status unavailable.",
                rpe_pending_style(0),
                [],
                None,
            )
        pending = pending_gym_sessions(exercises)
        options = rpe_session_options(pending)
        value = options[0]["value"] if options else None
        count = len(pending)
        return (
            rpe_pending_style(count),
            rpe_pending_children(count),
            rpe_pending_message(count),
            rpe_pending_style(count),
            options,
            value,
        )

    @app.callback(
        Output("rpe-modal", "opened"),
        Output("rpe-feedback", "children"),
        Output("rpe-value", "value"),
        Output("rpe-refresh", "data"),
        Output("metric-refresh", "data"),
        Input("rpe-pending-btn", "n_clicks"),
        Input("rpe-card-open", "n_clicks"),
        Input("rpe-save", "n_clicks"),
        Input("rpe-cancel", "n_clicks"),
        Input("rpe-apply", "n_clicks"),
        State("rpe-session-select", "value"),
        State("rpe-value", "value"),
        State("rpe-refresh", "data"),
        State("metric-refresh", "data"),
        prevent_initial_call=True,
    )
    def handle_rpe(  # noqa: PLR0911, PLR0917
        _open: int | None,
        _card_open: int | None,
        _save: int | None,
        _cancel: int | None,
        _apply: int | None,
        exercise_id: str | None,
        rpe: float | None,
        counter: int | None,
        metrics: int | None,
    ) -> tuple[bool, str, float | None, int, int]:
        """Open/close the modal, save RPEs and refresh the dashboard."""
        current = counter or 0
        metrics_current = metrics or 0
        if ctx.triggered_id in {"rpe-pending-btn", "rpe-card-open"}:
            return (True, "", None, current, metrics_current)
        if ctx.triggered_id == "rpe-cancel":
            return (False, "", None, current, metrics_current)
        if exercise_id is None or rpe is None:
            return (True, "Select a session and enter an RPE.", None, current, metrics_current)
        if not 0.0 <= float(rpe) <= _MAX_RPE:
            return (
                True,
                "RPE must be between 0 and 10.",
                None,
                current,
                metrics_current,
            )
        try:
            client.set_rpe(exercise_id, float(rpe))
        except MetricsClientError:
            return (
                True,
                "Could not save the RPE (backend offline).",
                None,
                current,
                metrics_current,
            )
        if ctx.triggered_id == "rpe-apply":
            return (False, "", None, current + 1, metrics_current + 1)
        return (True, "RPE saved. Select the next session.", None, current + 1, metrics_current + 1)


def _register_race_taper_callbacks(app: dash.Dash, client: MetricsClient) -> None:
    """Register the race-taper plan-generation callback."""

    @app.callback(
        Output("race-chart", "figure"),
        Output("race-plan-status", "children"),
        Input("race-run", "n_clicks"),
        State("race-date", "value"),
        State("race-base-km", "value"),
        State("race-runs", "value"),
        State("race-pace", "value"),
        State("race-rpe", "value"),
        State("race-weeks", "value"),
        prevent_initial_call=True,
    )
    def run_taper_plan(  # noqa: PLR0917
        _clicks: int | None,
        race_date: str | None,
        base_km: float | None,
        runs: int | None,
        pace: float | None,
        rpe: float | None,
        weeks: int | None,
    ) -> tuple[object, str]:
        """Generate the pre-race taper and project it to race morning."""
        if (
            race_date is None
            or base_km is None
            or runs is None
            or pace is None
            or rpe is None
            or weeks is None
        ):
            return (
                cast(object, build_taper_figure(TaperSimulationResponse())),
                "Complete every field before planning.",
            )
        try:
            target = date.fromisoformat(race_date)
            calibration = client.get_calibration()
            plan = client.post_taper_plan(
                TaperPlanRequest(
                    race_date=target,
                    base_weekly_km=float(base_km),
                    pace_min_per_km=float(pace),
                    runs_per_week=int(runs),
                    rpe=float(rpe),
                    taper_weeks=int(weeks),
                    params=calibration.params,
                )
            )
        except (MetricsClientError, ValueError):
            return (
                cast(object, build_taper_figure(TaperSimulationResponse())),
                "Backend offline or invalid input.",
            )
        figure = build_taper_figure(plan.simulation, race_date=plan.race_date)
        freshness = plan.race_freshness
        freshness_text = "n/a" if freshness is None else f"{freshness:.1f}"
        status = (
            f"{len(plan.sessions)} sessions over {len(plan.weeks)} weeks · "
            f"race freshness {freshness_text} · model: {_model_label(calibration)}"
        )
        return (cast(object, figure), status)


app = create_app()
server = app.server


if __name__ == "__main__":  # pragma: no cover
    debug = os.environ.get("DASH_DEBUG", "true").lower() not in {"0", "false", "no"}
    app.run(debug=debug, host="0.0.0.0", port=8050)
