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


class EkfCalibrationResponse(BaseModel):
    """Calibrated Banister parameters and their validation (``RF-03.2``)."""

    params: BanisterParams = Field(description="Effective parameters (calibrated or prior).")
    priors: BanisterParams = Field(description="Reference priors used as the fallback.")
    calibrated: bool = Field(description="Whether the fit passed the quality gate.")
    observations: int = Field(ge=0, description="Number of observed performance points.")
    r_squared: float | None = Field(
        default=None, description="Coefficient of determination of the fit, if computable."
    )
    baseline_efficiency: float | None = Field(
        default=None, description="Median efficiency factor used to normalise observations."
    )


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


class RunningBaselineResponse(BaseModel):
    """Recent weekly running volume used as the taper starting point (``S14``)."""

    weekly_km: float = Field(ge=0.0, description="Average weekly distance in kilometres.")
    runs_per_week: int = Field(ge=1, description="Average number of runs per week.")
    pace_min_per_km: float = Field(gt=0.0, description="Average pace in minutes per kilometre.")
    rpe: float = Field(ge=0.0, le=10.0, description="Average session RPE.")
    sessions: int = Field(ge=0, description="Number of sessions in the baseline window.")
    weeks: int = Field(ge=1, description="Weeks covered by the baseline window.")


class TaperWeekSummary(BaseModel):
    """Weekly volume of a taper plan, oldest week first."""

    start: date = Field(description="Monday that starts the week.")
    factor: float = Field(gt=0.0, description="Fraction of the base weekly volume.")
    distance_km: float = Field(ge=0.0, description="Planned distance in kilometres.")
    sessions: int = Field(ge=0, description="Number of planned sessions.")


class TaperPlanRequest(BaseModel):
    """Inputs to generate a progressive pre-race taper (``RF-05.2``, ``S14``)."""

    race_date: date
    base_weekly_km: float = Field(gt=0.0, description="Current weekly running volume.")
    pace_min_per_km: float = Field(gt=0.0, description="Planned pace in minutes per kilometre.")
    runs_per_week: int = Field(default=3, ge=1, le=7, description="Running sessions per week.")
    rpe: float = Field(default=6.0, ge=0.0, le=10.0, description="Planned session RPE.")
    taper_weeks: int = Field(default=3, ge=1, le=8, description="Taper length in weeks.")
    params: BanisterParams | None = Field(
        default=None,
        description="Override the physiological priors; defaults to ``/config/physiology``.",
    )


class TaperPlanResponse(BaseModel):
    """Generated taper sessions and their projection up to race day."""

    sessions: list[PlannedSession] = Field(default_factory=list)
    weeks: list[TaperWeekSummary] = Field(default_factory=list)
    simulation: TaperSimulationResponse = Field(default_factory=TaperSimulationResponse)
    race_date: date
    race_index: int = Field(ge=-1, description="Index of race day in the projection, or -1.")
    race_freshness: float | None = Field(
        default=None, description="Projected freshness on race morning."
    )
    peak_freshness_date: date | None = Field(
        default=None, description="Day with the highest freshness inside the taper window."
    )
    peak_freshness: float | None = Field(
        default=None, description="Highest freshness inside the taper window."
    )
