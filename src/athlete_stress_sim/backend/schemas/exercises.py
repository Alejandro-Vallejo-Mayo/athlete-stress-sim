"""Pydantic request/response models for the exercises endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
