"""REST endpoints exposing the training-load metrics and the simulator (S10, S13).

Metrics are computed on demand from the persisted DuckDB sessions: the Banister
TRIMP for endurance sessions and the session-RPE load for strength sessions feed
the ACWR (``RF-04``) and the fitness-fatigue model (``RF-03``). ``POST /simulate``
runs the Banister model forward over a caller-provided daily-load series, while
``POST /simulate/taper`` merges planned sessions with the history (``RF-05.2``)
and ``GET /metrics/decoupling/{id}`` reports the aerobic decoupling (``RF-05.3``).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.schemas.metrics import (
    AcwrPoint,
    AcwrResponse,
    BanisterSeriesResponse,
    DecouplingResponse,
    SessionLoadResponse,
    SimulationRequest,
    SimulationResponse,
    TaperSimulationRequest,
    TaperSimulationResponse,
)
from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.core.etl.types import Exercise
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
from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response
from athlete_stress_sim.core.storage.session_store import SessionStore

router = APIRouter(prefix="/metrics", tags=["metrics"])
simulate_router = APIRouter(tags=["simulation"])

SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]


def _physiology_params() -> BanisterParams:
    """Build the Banister parameters from the active physiological priors."""
    return BanisterParams(
        p0=physiology.p0,
        k1=physiology.k_1,
        k2=physiology.k_2,
        tau1=physiology.tau_1,
        tau2=physiology.tau_2,
    )


def _exercise_load(store: SessionStore, exercise: Exercise) -> float | None:
    """Compute one exercise's internal load (TRIMP or session-RPE)."""
    hr_samples: list[int | None] | None
    if is_strength(exercise.sport, exercise.sub_sport):
        hr_samples = None
    else:
        hr_samples = [sample.hr for sample in store.query_samples(exercise.exercise_id)]
    return session_load(
        exercise.sport,
        exercise.sub_sport,
        hr_samples=hr_samples,
        duration_s=exercise.duration_s,
        rpe=store.get_rpe(exercise.exercise_id),
        hr_rest=physiology.hr_rest,
        hr_max=physiology.hr_max,
        sex=physiology.sex,
    )


def _assemble_daily_loads(store: SessionStore) -> list[tuple[date, float]]:
    """Collect every computable session load keyed by its calendar date."""
    dated_loads: list[tuple[date, float]] = []
    for exercise in store.list_exercises():
        if exercise.start_time is None:
            continue
        load = _exercise_load(store, exercise)
        if load is not None:
            dated_loads.append((exercise.start_time.date(), load))
    return dated_loads


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
        load=_exercise_load(store, exercise),
    )


@router.get("/acwr")
def get_acwr(store: SessionStoreDep) -> AcwrResponse:
    """Return the daily acute:chronic workload ratio series and risk zones."""
    dates, values = daily_load_series(_assemble_daily_loads(store))
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
    dates, values = daily_load_series(_assemble_daily_loads(store))
    result = impulse_response(values, _physiology_params())
    return BanisterSeriesResponse(
        dates=dates,
        fitness=result.fitness,
        fatigue=result.fatigue,
        performance=result.performance,
        freshness=result.freshness,
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
    history = _assemble_daily_loads(store)
    history_dates = {day for day, _ in history}
    planned = [
        (
            session.date,
            planned_session_load(session.distance_km, session.pace_min_per_km, session.rpe),
        )
        for session in payload.sessions
    ]
    dates, values = daily_load_series([*history, *planned])
    result = impulse_response(values, payload.params or _physiology_params())
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
