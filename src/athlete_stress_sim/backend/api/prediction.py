"""Race time prediction endpoints (``RF-05.4``).

The endpoints expose the best running efforts found in the persisted history and
a race-time prediction anchored on those efforts and/or a user-provided race or
time trial. Effort intensity (heart-rate reserve) and the Banister fitness trend
are used so an easy run is not mistaken for a slow race potential.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.backend.api.metrics import _assemble_daily_loads, _calibration
from athlete_stress_sim.backend.config import physiology
from athlete_stress_sim.backend.schemas.prediction import (
    EffortOut,
    RacePredictionRequest,
    RacePredictionResponse,
    RaceReference,
)
from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.core.etl.types import Sample
from athlete_stress_sim.core.metrics.load import daily_load_series
from athlete_stress_sim.core.metrics.race_prediction import (
    Effort,
    EffortSource,
    EffortTier,
    RacePrediction,
    predict_race,
    select_best_efforts,
)
from athlete_stress_sim.core.models.banister import impulse_response
from athlete_stress_sim.core.storage.session_store import SessionStore

router = APIRouter(prefix="/metrics", tags=["prediction"])

SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]

_DISTANCES_KM = (1.0, 3.0, 5.0, 10.0, 21.0975)
_PREDICTION_WINDOW_DAYS = 180
_MIN_FITNESS_FACTOR = 0.8
_MAX_FITNESS_FACTOR = 1.2


def _running_sessions(store: SessionStore) -> list[tuple[date, list[Sample]]]:
    """Collect recent running activities with their telemetry."""
    exercises = [
        exercise
        for exercise in store.list_exercises()
        if exercise.start_time is not None and not is_strength(exercise.sport, exercise.sub_sport)
    ]
    if not exercises:
        return []
    latest = max(exercise.start_time for exercise in exercises if exercise.start_time is not None)
    cutoff = latest.date() - timedelta(days=_PREDICTION_WINDOW_DAYS)
    sessions: list[tuple[date, list[Sample]]] = []
    for exercise in exercises:
        if exercise.start_time is None:
            continue
        day = exercise.start_time.date()
        if day < cutoff:
            continue
        samples = store.query_samples(exercise.exercise_id)
        if samples:
            sessions.append((day, samples))
    return sessions


def _detected_efforts(store: SessionStore) -> list[Effort]:
    """Return the best training effort per distance, fitness-adjusted."""
    sessions = _running_sessions(store)
    efforts = select_best_efforts(
        sessions,
        _DISTANCES_KM,
        hr_rest=physiology.hr_rest,
        hr_max=physiology.hr_max,
    )
    return _fitness_adjusted(store, efforts)


def _fitness_adjusted(store: SessionStore, efforts: list[Effort]) -> list[Effort]:
    """Scale each effort's time to the current Banister fitness level."""
    if not efforts:
        return []
    dates, values = daily_load_series(_assemble_daily_loads(store))
    if not dates:
        return efforts
    calibration = _calibration(store, dates, values)
    fitness = impulse_response(values, calibration.params).fitness
    if not fitness:
        return efforts
    current = fitness[-1]
    if current <= 0.0:
        return efforts
    index_by_date = {day: index for index, day in enumerate(dates)}
    adjusted: list[Effort] = []
    for effort in efforts:
        index = index_by_date.get(effort.day)
        if index is None or fitness[index] <= 0.0:
            adjusted.append(effort)
            continue
        factor = min(
            _MAX_FITNESS_FACTOR,
            max(_MIN_FITNESS_FACTOR, current / fitness[index]),
        )
        adjusted.append(replace(effort, fitness_factor=factor))
    return adjusted


def _manual_effort(reference: RaceReference, store: SessionStore) -> Effort:
    """Build a race-tier effort from the user-provided reference."""
    effort = Effort(
        distance_km=reference.distance_km,
        time_s=reference.time_s,
        day=reference.day or date.today(),
        avg_hr=None,
        relative_hr=None,
        efficiency=None,
        tier=EffortTier.RACE,
        source=EffortSource.MANUAL,
    )
    return _fitness_adjusted(store, [effort])[0]


def _to_out(effort: Effort) -> EffortOut:
    return EffortOut(
        distance_km=effort.distance_km,
        time_s=effort.time_s,
        day=effort.day,
        avg_hr=effort.avg_hr,
        relative_hr=effort.relative_hr,
        efficiency=effort.efficiency,
        tier=effort.tier,
        source=effort.source,
        fitness_factor=effort.fitness_factor,
    )


def _to_response(prediction: RacePrediction) -> RacePredictionResponse:
    return RacePredictionResponse(
        distance_km=prediction.distance_km,
        predicted_time_s=prediction.predicted_time_s,
        predicted_pace_s_per_km=prediction.predicted_pace_s_per_km,
        fast_time_s=prediction.fast_time_s,
        slow_time_s=prediction.slow_time_s,
        model=prediction.model,
        confidence=prediction.confidence,
        efforts=[_to_out(effort) for effort in prediction.efforts],
        notes=prediction.notes,
    )


@router.get("/best-efforts")
def get_best_efforts(store: SessionStoreDep) -> list[EffortOut]:
    """Return the best detected running effort for each reference distance."""
    return [_to_out(effort) for effort in _detected_efforts(store)]


@router.post("/race-prediction")
def predict_race_endpoint(
    payload: RacePredictionRequest,
    store: SessionStoreDep,
) -> RacePredictionResponse:
    """Predict a race time from detected efforts and/or a manual reference."""
    detected = _detected_efforts(store) if payload.use_detected_efforts else []
    manual = _manual_effort(payload.reference, store) if payload.reference else None
    prediction = predict_race(
        payload.distance_km,
        detected,
        model=payload.model,
        reference=manual,
        exponent=payload.exponent,
        hr_rest=physiology.hr_rest,
        hr_max=physiology.hr_max,
    )
    return _to_response(prediction)
