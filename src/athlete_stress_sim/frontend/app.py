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
from dash import Input, Output, State, ctx, dcc, html, no_update

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
    decoupling_summary,
)
from athlete_stress_sim.frontend.components.fitness_chart import fitness_panel
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
from athlete_stress_sim.frontend.components.sessions import recent_sessions_panel
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
from athlete_stress_sim.frontend.theme import COLORS, MANTINE_THEME

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
        cast(object, fitness_panel(series)),
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
        cast(object, fitness_panel(BanisterSeriesResponse())),
        cast(object, acwr_risk_panel([])),
        cast(object, freshness_panel(BanisterSeriesResponse())),
        cast(object, quick_stats_panel(None, [])),
        [],
        None,
        _offline_alert(),
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


def _trends_tab() -> dmc.Stack:
    """Build the historical view: training load, decoupling and sessions."""
    return dmc.Stack(
        [
            html.Div(fitness_panel(BanisterSeriesResponse()), id="fitness-panel"),
            decoupling_panel(),
            html.Div(recent_sessions_panel([]), id="recent-sessions"),
        ],
        gap="lg",
    )


def _plan_tab() -> dmc.Tabs:
    """Build the planning tools under internal tabs."""
    return dmc.Tabs(
        value="taper",
        keepMounted=True,
        variant="pills",
        children=[
            dmc.TabsList(
                [
                    dmc.TabsTab("Race taper", value="taper"),
                    dmc.TabsTab("What-if", value="simulator"),
                    dmc.TabsTab("Race predictor", value="predictor"),
                ],
                justify="left",
            ),
            dmc.TabsPanel(race_taper_panel(), value="taper", pt="md"),
            dmc.TabsPanel(simulator_panel(), value="simulator", pt="md"),
            dmc.TabsPanel(race_predictor_panel(), value="predictor", pt="md"),
        ],
    )


def create_app(client: MetricsClient | None = None) -> dash.Dash:
    """Build and configure the Dash app with a dark, performance-lab aesthetic."""
    metrics_client = client or MetricsClient()

    app = dash.Dash(__name__)
    app.title = "Athlete Stress Sim"

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
                                            _trends_tab(),
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
        Output("fitness-panel", "children"),
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
        Output("decoupling-summary", "children"),
        Input("decoupling-run", "value"),
    )
    def render_decoupling(exercise_id: str | None) -> tuple[object, object]:
        """Render the per-kilometre efficiency and session summary of a run."""
        if exercise_id is None:
            return (
                cast(object, build_decoupling_figure(DecouplingResponse(exercise_id=""))),
                decoupling_summary(None),
            )
        try:
            response = metrics_client.get_decoupling(exercise_id)
            exercises = metrics_client.get_exercises("run")
        except MetricsClientError:
            return (
                cast(object, build_decoupling_figure(DecouplingResponse(exercise_id=exercise_id))),
                dmc.Text("Backend offline.", size="sm", style={"color": COLORS["text_muted"]}),
            )
        exercise = next((item for item in exercises if item.exercise_id == exercise_id), None)
        return (
            cast(object, build_decoupling_figure(response)),
            decoupling_summary(response, exercise),
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
    _register_plan_prefill(app, metrics_client)
    return app


def _register_plan_prefill(app: dash.Dash, client: MetricsClient) -> None:
    """Prefill planning inputs from the recent running baseline on first load."""

    @app.callback(
        Output("race-base-km", "value"),
        Output("race-runs", "value"),
        Output("race-pace", "value"),
        Output("race-rpe", "value"),
        Output("sim-distance", "value"),
        Output("sim-pace", "value"),
        Output("sim-rpe", "value"),
        Input("init", "n_intervals"),
    )
    def prefill_plan_inputs(_interval: int | None) -> tuple[object, ...]:
        """Populate the plan forms with the athlete's recent running baseline."""
        try:
            baseline = client.get_running_baseline()
        except MetricsClientError:
            return (no_update,) * 7
        if baseline is None:
            return (no_update,) * 7
        weekly_km = round(baseline.weekly_km, 1)
        pace = round(baseline.pace_min_per_km, 1)
        rpe = round(baseline.rpe, 1)
        typical_km = max(1.0, round(weekly_km / baseline.runs_per_week, 1))
        return (
            weekly_km,
            baseline.runs_per_week,
            pace,
            rpe,
            typical_km,
            pace,
            rpe,
        )


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
        State("race-model", "value"),
        State("race-exponent", "value"),
        prevent_initial_call=True,
    )
    def run_race_prediction(  # noqa: PLR0917
        _clicks: int | None,
        preset: str | None,
        custom_distance_km: object,
        reference_distance_km: object,
        reference_minutes: object,
        model_value: str | None,
        exponent_value: object,
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
        model = PredictionModel(model_value) if model_value else PredictionModel.AUTO
        exponent = optional_float(exponent_value) or 1.06
        try:
            prediction = client.predict_race(
                RacePredictionRequest(
                    distance_km=target_distance,
                    model=model,
                    reference=reference,
                    exponent=exponent,
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
        Input("sessions-rpe-open", "n_clicks"),
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
        _sessions_open: int | None,
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
        if ctx.triggered_id in {"rpe-pending-btn", "rpe-card-open", "sessions-rpe-open"}:
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

    @app.callback(
        Output("recent-sessions", "children"),
        Input("data-refreshed", "data"),
    )
    def load_recent_sessions(_refreshed: int | None) -> object:
        """Load the latest sessions for the Trends view."""
        try:
            exercises = client.get_exercises("all")
        except MetricsClientError:
            exercises = []
        return recent_sessions_panel(exercises)


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
