"""Exercise endpoints: list sessions and record/read their session-RPE."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from athlete_stress_sim.backend.api.ingest import get_session_store
from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.core.etl.types import Exercise
from athlete_stress_sim.core.metrics.rpe import session_rpe_load
from athlete_stress_sim.core.storage.session_store import SessionStore

router = APIRouter(prefix="/exercises", tags=["exercises"])

SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]


class RpeInput(BaseModel):
    """Request body to record a session's RPE."""

    rpe: float = Field(ge=0, le=10, description="Borg CR-10 session RPE (0-10).")


class ExerciseOut(BaseModel):
    """Exercise summary with its RPE and computed strength load, if any."""

    exercise_id: str
    sport: str = ""
    sub_sport: str = ""
    start_time: datetime | None = None
    duration_s: float | None = None
    distance_m: float | None = None
    avg_hr: int | None = None
    rpe: float | None = None
    load: float | None = None


def _to_out(exercise: Exercise, rpe: float | None) -> ExerciseOut:
    load: float | None = None
    if rpe is not None and exercise.duration_s is not None:
        load = session_rpe_load(rpe, exercise.duration_s)
    return ExerciseOut(
        exercise_id=exercise.exercise_id,
        sport=exercise.sport,
        sub_sport=exercise.sub_sport,
        start_time=exercise.start_time,
        duration_s=exercise.duration_s,
        distance_m=exercise.distance_m,
        avg_hr=exercise.avg_hr,
        rpe=rpe,
        load=load,
    )


@router.get("")
def list_exercises(
    store: SessionStoreDep,
    kind: Literal["all", "gym"] = "all",
) -> list[ExerciseOut]:
    """List persisted exercises, optionally only strength/gym sessions."""
    result: list[ExerciseOut] = []
    for exercise in store.list_exercises():
        if kind == "gym" and not is_strength(exercise.sport, exercise.sub_sport):
            continue
        result.append(_to_out(exercise, store.get_rpe(exercise.exercise_id)))
    return result


@router.get("/{exercise_id}")
def get_exercise(exercise_id: str, store: SessionStoreDep) -> ExerciseOut:
    """Return one exercise with its RPE and computed load."""
    exercise = store.get_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail=f"Unknown exercise {exercise_id!r}.")
    return _to_out(exercise, store.get_rpe(exercise_id))


@router.post("/{exercise_id}/rpe")
def set_rpe(exercise_id: str, payload: RpeInput, store: SessionStoreDep) -> ExerciseOut:
    """Record the session-RPE (Borg CR-10) for an exercise."""
    exercise = store.get_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail=f"Unknown exercise {exercise_id!r}.")
    store.set_rpe(exercise_id, payload.rpe)
    return _to_out(exercise, payload.rpe)
