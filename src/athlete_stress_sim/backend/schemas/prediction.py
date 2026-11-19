"""Request/response models for the race prediction endpoints (``RF-05.4``)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from athlete_stress_sim.core.metrics.race_prediction import (
    Confidence,
    EffortSource,
    EffortTier,
    PredictionModel,
)


class EffortOut(BaseModel):
    """A detected best effort with its intensity and fitness adjustment."""

    distance_km: float
    time_s: float
    day: date
    avg_hr: float | None = None
    relative_hr: float | None = None
    efficiency: float | None = None
    tier: EffortTier
    source: EffortSource = EffortSource.TRAINING
    fitness_factor: float = 1.0


class RaceReference(BaseModel):
    """A user-provided race or time-trial reference."""

    distance_km: float = Field(gt=0.0, description="Reference distance in kilometres.")
    time_s: float = Field(gt=0.0, description="Reference time in seconds.")
    day: date | None = Field(default=None, description="Date of the reference effort.")


class RacePredictionRequest(BaseModel):
    """Inputs to predict a race time (``RF-05.4``)."""

    distance_km: float = Field(gt=0.0, le=200.0, description="Target race distance.")
    model: PredictionModel = Field(
        default=PredictionModel.AUTO,
        description="Requested model; ``auto`` selects the best available one.",
    )
    reference: RaceReference | None = Field(
        default=None, description="Optional race/time-trial reference."
    )
    use_detected_efforts: bool = Field(
        default=True, description="Use best efforts detected in training."
    )
    exponent: float = Field(default=1.06, ge=0.5, le=1.5, description="Riegel exponent.")


class RacePredictionResponse(BaseModel):
    """Predicted race time, support range and the efforts used."""

    distance_km: float
    predicted_time_s: float | None = None
    predicted_pace_s_per_km: float | None = None
    fast_time_s: float | None = None
    slow_time_s: float | None = None
    model: PredictionModel
    confidence: Confidence
    efforts: list[EffortOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
