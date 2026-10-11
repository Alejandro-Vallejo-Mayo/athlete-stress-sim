"""Pydantic request/response models for the metrics and simulation endpoints (S10)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from athlete_stress_sim.core.metrics.acwr import RiskZone
from athlete_stress_sim.core.models.banister import BanisterParams


class SessionLoadResponse(BaseModel):
    """Internal training load of a single session (``RF-02``)."""

    exercise_id: str
    sport: str
    sub_sport: str
    start_time: datetime | None = None
    load: float | None = Field(
        default=None,
        description="Banister TRIMP (endurance) or session-RPE load (strength), if computable.",
    )


class AcwrPoint(BaseModel):
    """Acute:chronic workload ratio evaluated on a single day (``RF-04``)."""

    date: date
    acute: float = Field(description="7-day EWMA (acute load).")
    chronic: float = Field(description="28-day EWMA (chronic load).")
    acwr: float = Field(description="Acute:chronic ratio.")
    zone: RiskZone = Field(description="Injury-risk zone derived from the ratio.")


class AcwrResponse(BaseModel):
    """Daily ACWR series over the persisted training history."""

    points: list[AcwrPoint] = Field(default_factory=list)


class BanisterSeriesResponse(BaseModel):
    """Per-day fitness-fatigue model output aligned with calendar dates (``RF-03.1``)."""

    dates: list[date] = Field(default_factory=list)
    fitness: list[float] = Field(default_factory=list)
    fatigue: list[float] = Field(default_factory=list)
    performance: list[float] = Field(default_factory=list)
    freshness: list[float] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    """Daily loads to simulate, with optional parameter overrides (``RF-05.2``)."""

    daily_loads: list[float] = Field(
        min_length=1, description="One training-load value per day (rest days = 0.0)."
    )
    params: BanisterParams | None = Field(
        default=None,
        description="Override the physiological priors; defaults to ``/config/physiology``.",
    )


class SimulationResponse(BaseModel):
    """Simulated fitness-fatigue trajectory for the requested daily loads."""

    fitness: list[float] = Field(default_factory=list)
    fatigue: list[float] = Field(default_factory=list)
    performance: list[float] = Field(default_factory=list)
    freshness: list[float] = Field(default_factory=list)


class DecouplingResponse(BaseModel):
    """Aerobic decoupling of a running session (``RF-05.3``)."""

    exercise_id: str
    efficiency_per_km: list[float] = Field(
        default_factory=list, description="Efficiency factor (speed/HR) per kilometre."
    )
    decoupling_pct: float | None = Field(
        default=None, description="Relative EF drop from the first to the second half."
    )


class PlannedSession(BaseModel):
    """A projected future running session (``RF-05.2``)."""

    date: date
    distance_km: float = Field(gt=0.0, description="Planned distance in kilometres.")
    pace_min_per_km: float = Field(gt=0.0, description="Planned pace in minutes per kilometre.")
    rpe: float = Field(ge=0.0, le=10.0, description="Planned Borg CR-10 session RPE.")


class TaperSimulationRequest(BaseModel):
    """Planned sessions to project on top of the persisted history (``RF-05.2``)."""

    sessions: list[PlannedSession] = Field(default_factory=list)
    params: BanisterParams | None = Field(
        default=None,
        description="Override the physiological priors; defaults to ``/config/physiology``.",
    )


class TaperSimulationResponse(BaseModel):
    """Dated fitness-fatigue trajectory with a marked history/forecast boundary."""

    dates: list[date] = Field(default_factory=list)
    fitness: list[float] = Field(default_factory=list)
    fatigue: list[float] = Field(default_factory=list)
    performance: list[float] = Field(default_factory=list)
    freshness: list[float] = Field(default_factory=list)
    history_end_index: int = Field(
        default=-1,
        description="Index of the last real (history) day, or -1 when there is no history.",
    )
