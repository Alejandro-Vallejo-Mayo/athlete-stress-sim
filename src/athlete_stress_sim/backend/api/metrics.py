"""REST endpoints exposing the training-load metrics and the simulator (S10, S13).

Metrics are computed on demand from the persisted DuckDB sessions: the Banister
TRIMP for endurance sessions and the session-RPE load for strength sessions feed
the ACWR (``RF-04``) and the fitness-fatigue model (``RF-03``). ``POST /simulate``
runs the Banister model forward over a caller-provided daily-load series, while
``POST /simulate/taper`` merges planned sessions with the history (``RF-05.2``),
``POST /simulate/taper/plan`` generates a tapering plan up to race day (``S14``),
``GET /metrics/running-baseline`` reports the recent weekly running volume and
``GET /metrics/decoupling/{id}`` reports the aerobic decoupling (``RF-05.3``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.schemas.metrics import (
    AcwrPoint,
    AcwrResponse,
    BanisterSeriesResponse,
    CalibrationResponse,
    DecouplingResponse,
    PlannedSession,
    RunningBaselineResponse,
    SessionLoadResponse,
    SimulationRequest,
    SimulationResponse,
    TaperPlanRequest,
    TaperPlanResponse,
    TaperSimulationRequest,
    TaperSimulationResponse,
    TaperWeekSummary,
)
from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.core.etl.types import Exercise, SampleLike
from athlete_stress_sim.core.metrics.acwr import (
    DEFAULT_ACUTE_DAYS,
    DEFAULT_CHRONIC_DAYS,
    acwr_series,
    classify_risk,
    ewma_lambda,
    ewma_series,
)
from athlete_stress_sim.core.metrics.decoupling import aerobic_decoupling, per_km_efficiency
from athlete_stress_sim.core.metrics.load import (
    daily_load_series,
    planned_session_load,
    session_load,
)
from athlete_stress_sim.core.metrics.performance import (
    performance_observations,
    session_efficiency,
)
from athlete_stress_sim.core.metrics.taper import (
    build_taper_sessions,
    running_baseline,
)
from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response
from athlete_stress_sim.core.models.calibration import CalibrationResult, calibrate_banister
from athlete_stress_sim.core.storage.session_store import SessionStore

router = APIRouter(prefix="/metrics", tags=["metrics"])
simulate_router = APIRouter(tags=["simulation"])

SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]


@dataclass(frozen=True)
class _SessionData:
    """Exercises, their RPE and telemetry loaded from DuckDB in one batch."""

    exercises: list[tuple[Exercise, float | None]]
    samples: Mapping[str, Sequence[SampleLike]]


_SESSION_DATA_CACHE: dict[str, tuple[tuple[str, int, int, int], _SessionData]] = {}
_SESSION_DATA_CACHE_MAX = 8


def _load_session_data(store: SessionStore) -> _SessionData:
    """Load every exercise, RPE and sample with a constant number of queries.

    The snapshot is cached per database file and invalidated by its revision
    (mtime, size and the store's own write counter), so repeated dashboard calls
    reuse it while RPE edits and syncs still produce fresh data.
    """
    revision = store.revision()
    cached = _SESSION_DATA_CACHE.get(revision[0])
    if cached is not None and cached[0] == revision:
        return cached[1]
    data = _SessionData(
        exercises=store.list_exercises_with_rpe(),
        samples=store.query_all_samples(),
    )
    if len(_SESSION_DATA_CACHE) >= _SESSION_DATA_CACHE_MAX:
        _SESSION_DATA_CACHE.pop(next(iter(_SESSION_DATA_CACHE)))
    _SESSION_DATA_CACHE[revision[0]] = (revision, data)
    return data


def _physiology_params() -> BanisterParams:
    """Build the Banister parameters from the active physiological priors."""
    return BanisterParams(
        p0=physiology.p0,
        k1=physiology.k_1,
        k2=physiology.k_2,
        tau1=physiology.tau_1,
        tau2=physiology.tau_2,
    )


def _exercise_load(
    exercise: Exercise,
    samples: Sequence[SampleLike],
    rpe: float | None,
) -> float | None:
    """Compute one exercise's internal load (TRIMP or session-RPE)."""
    hr_samples: list[int | None] | None
    if is_strength(exercise.sport, exercise.sub_sport):
        hr_samples = None
    else:
        hr_samples = [sample.hr for sample in samples]
    return session_load(
        exercise.sport,
        exercise.sub_sport,
        hr_samples=hr_samples,
        duration_s=exercise.duration_s,
        rpe=rpe,
        hr_rest=physiology.hr_rest,
        hr_max=physiology.hr_max,
        sex=physiology.sex,
    )


def _assemble_daily_loads(data: _SessionData) -> list[tuple[date, float]]:
    """Collect every computable session load keyed by its calendar date."""
    dated_loads: list[tuple[date, float]] = []
    for exercise, rpe in data.exercises:
        if exercise.start_time is None:
            continue
        samples = data.samples.get(exercise.exercise_id, [])
        load = _exercise_load(exercise, samples, rpe)
        if load is not None:
            dated_loads.append((exercise.start_time.date(), load))
    return dated_loads


def _assemble_performance(data: _SessionData, dates: list[date]) -> dict[int, float]:
    """Collect the efficiency factor of every running session keyed by day index."""
    sessions: list[tuple[date, float | None]] = []
    for exercise, _ in data.exercises:
        if exercise.start_time is None or is_strength(exercise.sport, exercise.sub_sport):
            continue
        samples = data.samples.get(exercise.exercise_id, [])
        sessions.append((exercise.start_time.date(), session_efficiency(samples)))
    return performance_observations(dates, sessions)


def _calibration(
    data: _SessionData,
    dates: list[date],
    daily_loads: list[float],
) -> CalibrationResult:
    """Calibrate the Banister parameters against the observed performance."""
    observations = _assemble_performance(data, dates)
    return calibrate_banister(daily_loads, observations, _physiology_params())


def _assemble_running_sessions(
    exercises: list[tuple[Exercise, float | None]],
) -> list[tuple[date, float, float | None, float | None]]:
    """Collect running sessions with distance, duration and RPE for the baseline."""
    sessions: list[tuple[date, float, float | None, float | None]] = []
    for exercise, rpe in exercises:
        if exercise.start_time is None or is_strength(exercise.sport, exercise.sub_sport):
            continue
        if exercise.distance_m is None or exercise.distance_m <= 0.0:
            continue
        sessions.append(
            (
                exercise.start_time.date(),
                exercise.distance_m / 1000.0,
                exercise.duration_s,
                rpe,
            )
        )
    return sessions


def _taper_response(
    history: list[tuple[date, float]],
    planned: list[tuple[date, float]],
    params: BanisterParams,
    *,
    extend_to: date | None = None,
) -> TaperSimulationResponse:
    """Run the fitness-fatigue model over history plus planned sessions.

    When ``extend_to`` is later than the last session, the daily series is padded
    with zero-load days so the projection reaches that date (e.g. race morning).
    """
    dates, values = daily_load_series([*history, *planned])
    if extend_to is not None:
        if not dates:
            dates, values = [extend_to], [0.0]
        else:
            current = dates[-1] + timedelta(days=1)
            while current <= extend_to:
                dates.append(current)
                values.append(0.0)
                current += timedelta(days=1)
    result = impulse_response(values, params)
    history_dates = {day for day, _ in history}
    history_end_index = -1
    if history_dates:
        last_history = max(history_dates)
        if last_history in dates:
            history_end_index = dates.index(last_history)
    return TaperSimulationResponse(
        dates=dates,
        fitness=result.fitness,
        fatigue=result.fatigue,
        performance=result.performance,
        freshness=result.freshness,
        history_end_index=history_end_index,
    )


@router.get("/trimp/{exercise_id}")
def get_session_trimp(exercise_id: str, store: SessionStoreDep) -> SessionLoadResponse:
    """Return the internal load of one session, if computable."""
    exercise = store.get_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail=f"Unknown exercise {exercise_id!r}.")
    return SessionLoadResponse(
        exercise_id=exercise.exercise_id,
        sport=exercise.sport,
        sub_sport=exercise.sub_sport,
        start_time=exercise.start_time,
        load=_exercise_load(
            exercise,
            store.query_samples(exercise.exercise_id),
            store.get_rpe(exercise.exercise_id),
        ),
    )


@router.get("/acwr")
def get_acwr(store: SessionStoreDep) -> AcwrResponse:
    """Return the daily acute:chronic workload ratio series and risk zones."""
    data = _load_session_data(store)
    dates, values = daily_load_series(_assemble_daily_loads(data))
    acute = ewma_series(values, ewma_lambda(DEFAULT_ACUTE_DAYS))
    chronic = ewma_series(values, ewma_lambda(DEFAULT_CHRONIC_DAYS))
    ratios = acwr_series(values)
    points = [
        AcwrPoint(date=day, acute=a, chronic=c, acwr=ratio, zone=classify_risk(ratio))
        for day, a, c, ratio in zip(dates, acute, chronic, ratios, strict=True)
    ]
    return AcwrResponse(points=points)


@router.get("/banister")
def get_banister(store: SessionStoreDep) -> BanisterSeriesResponse:
    """Return the fitness-fatigue trajectory for the persisted training history."""
    data = _load_session_data(store)
    dates, values = daily_load_series(_assemble_daily_loads(data))
    calibration = _calibration(data, dates, values)
    result = impulse_response(values, calibration.params)
    return BanisterSeriesResponse(
        dates=dates,
        fitness=result.fitness,
        fatigue=result.fatigue,
        performance=result.performance,
        freshness=result.freshness,
    )


@router.get("/ekf", deprecated=True)
@router.get("/calibration")
def get_calibration(store: SessionStoreDep) -> CalibrationResponse:
    """Return the calibrated Banister parameters and their validation."""
    data = _load_session_data(store)
    dates, values = daily_load_series(_assemble_daily_loads(data))
    calibration = _calibration(data, dates, values)
    return CalibrationResponse(
        params=calibration.params,
        priors=calibration.priors,
        calibrated=calibration.calibrated,
        observations=calibration.observations,
        r_squared=calibration.r_squared,
        baseline_efficiency=calibration.baseline_efficiency,
        cv_rmse=calibration.cv_rmse,
        prior_cv_rmse=calibration.prior_cv_rmse,
        cv_improvement=calibration.cv_improvement,
    )


@router.get("/running-baseline")
def get_running_baseline(store: SessionStoreDep) -> RunningBaselineResponse | None:
    """Return the recent weekly running volume used to seed the taper form."""
    sessions = _assemble_running_sessions(store.list_exercises_with_rpe())
    if not sessions:
        return None
    reference = max(session[0] for session in sessions) + timedelta(days=1)
    baseline = running_baseline(sessions, reference_date=reference)
    if baseline is None:
        return None
    return RunningBaselineResponse(
        weekly_km=baseline.weekly_km,
        runs_per_week=baseline.runs_per_week,
        pace_min_per_km=baseline.pace_min_per_km,
        rpe=baseline.rpe,
        sessions=baseline.sessions,
        weeks=baseline.weeks,
    )


@router.get("/decoupling/{exercise_id}")
def get_decoupling(exercise_id: str, store: SessionStoreDep) -> DecouplingResponse:
    """Return the per-kilometre efficiency factors and aerobic decoupling."""
    exercise = store.get_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail=f"Unknown exercise {exercise_id!r}.")
    samples = store.query_samples(exercise_id)
    return DecouplingResponse(
        exercise_id=exercise_id,
        efficiency_per_km=per_km_efficiency(samples),
        decoupling_pct=aerobic_decoupling(samples),
    )


@simulate_router.post("/simulate")
def simulate(payload: SimulationRequest) -> SimulationResponse:
    """Run the Banister model forward over the requested daily loads."""
    result = impulse_response(payload.daily_loads, payload.params or _physiology_params())
    return SimulationResponse(
        fitness=result.fitness,
        fatigue=result.fatigue,
        performance=result.performance,
        freshness=result.freshness,
    )


@simulate_router.post("/simulate/taper")
def simulate_taper(
    payload: TaperSimulationRequest,
    store: SessionStoreDep,
) -> TaperSimulationResponse:
    """Project the fitness-fatigue model over planned sessions plus history."""
    planned = [
        (
            session.date,
            planned_session_load(session.distance_km, session.pace_min_per_km, session.rpe),
        )
        for session in payload.sessions
    ]
    data = _load_session_data(store)
    return _taper_response(
        _assemble_daily_loads(data),
        planned,
        payload.params or _physiology_params(),
    )


@simulate_router.post("/simulate/taper/plan")
def plan_taper(
    payload: TaperPlanRequest,
    store: SessionStoreDep,
) -> TaperPlanResponse:
    """Generate a progressive taper up to race day and project it over history."""
    data = _load_session_data(store)
    history = _assemble_daily_loads(data)
    if history and payload.race_date <= max(day for day, _ in history):
        raise HTTPException(
            status_code=422,
            detail="race_date must be after the last recorded session.",
        )
    sessions, weeks = build_taper_sessions(
        race_date=payload.race_date,
        base_weekly_km=payload.base_weekly_km,
        pace_min_per_km=payload.pace_min_per_km,
        runs_per_week=payload.runs_per_week,
        rpe=payload.rpe,
        taper_weeks=payload.taper_weeks,
    )
    planned = [
        (
            session.date,
            planned_session_load(session.distance_km, session.pace_min_per_km, session.rpe),
        )
        for session in sessions
    ]
    simulation = _taper_response(
        history,
        planned,
        payload.params or _physiology_params(),
        extend_to=payload.race_date,
    )
    race_index = simulation.dates.index(payload.race_date)
    window_start = max(0, race_index - payload.taper_weeks * 7)
    peak_index = max(
        range(window_start, race_index + 1),
        key=lambda index: simulation.freshness[index],
    )
    return TaperPlanResponse(
        sessions=[
            PlannedSession(
                date=session.date,
                distance_km=session.distance_km,
                pace_min_per_km=session.pace_min_per_km,
                rpe=session.rpe,
            )
            for session in sessions
        ],
        weeks=[
            TaperWeekSummary(
                start=week.start,
                factor=week.factor,
                distance_km=week.distance_km,
                sessions=week.sessions,
            )
            for week in weeks
        ],
        simulation=simulation,
        race_date=payload.race_date,
        race_index=race_index,
        race_freshness=simulation.freshness[race_index],
        peak_freshness_date=simulation.dates[peak_index],
        peak_freshness=simulation.freshness[peak_index],
    )
