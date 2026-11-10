"""Race time prediction from training efforts (``RF-05.4``).

The predictor is effort-aware: it does not treat a slow easy run as a slow race.
Each candidate effort is classified by its relative heart-rate reserve
(``%HRR``) and its efficiency factor (``speed / HR``), so a fast pace at high
heart rate and a slow pace at low heart rate are compared fairly.

Two models are supported:

* Riegel's power law, ``T2 = T1 * (D2 / D1) ** k``, anchored on the best
  available race/hard effort (or a user-provided reference).
* Critical speed, ``D = CS * T + D'``, fitted to at least two quality efforts.

When only easy efforts exist the predictor extrapolates speed from the
efficiency factor and a race-level heart rate, and reports low confidence rather
than returning an artificially slow time.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import numpy as np

from athlete_stress_sim.core.etl.types import SampleLike

_METERS_PER_KM = 1000.0
_MIN_POINTS = 2
_MIN_CS_EFFORTS = 2
_MIN_QUALITY_EFFORTS = 3
_MIN_CS_R_SQUARED = 0.9
_MIN_TIME_RATIO = 1.2
_CS_RANGE = 0.02
_FITNESS_ALPHA = 0.1
_FITNESS_FACTOR_MIN = 0.8
_FITNESS_FACTOR_MAX = 1.2
_MIN_HR_CORRECTION = 1.0
_MAX_HR_CORRECTION = 1.15
_SHORT_RACE_KM = 6.0
_MEDIUM_RACE_KM = 12.0
_LONG_RACE_KM = 25.0
_SHORT_RACE_HR_RATIO = 0.93
_MEDIUM_RACE_HR_RATIO = 0.90
_LONG_RACE_HR_RATIO = 0.88
_ULTRA_RACE_HR_RATIO = 0.85
_HIGH_CONFIDENCE_RATIO = 3.0
_MEDIUM_CONFIDENCE_RATIO = 5.0
_LOW_CONFIDENCE_RANGE = 0.15
_DEFAULT_EXPONENT = 1.06
_SLOW_EXPONENT = 1.08
_MIN_EXPONENT = 0.5
_MAX_EXPONENT = 1.5
_HIGH_CS_R_SQUARED = 0.97
_FITNESS_EPS = 1e-6
_EASY_SLOW_PENALTY = 1.08
_MODERATE_SLOW_PENALTY = 1.03
_HARD_RANGE = 0.02
_MODERATE_RANGE = 0.04
_EASY_RANGE = 0.08

RACE_HR_RATIO = 0.88
"""Relative heart-rate reserve considered race effort."""

HARD_HR_RATIO = 0.80
"""Relative heart-rate reserve considered a hard effort."""

MODERATE_HR_RATIO = 0.70
"""Relative heart-rate reserve considered a moderate effort."""


def race_hr_ratio_for_distance(distance_km: float) -> float:
    """Return the target race-level heart-rate reserve for a distance.

    Shorter races are run closer to maximal heart rate. These targets are
    conservative population values: 5k/3k/1k ~93%, 10k ~90%, half ~88% and
    marathon ~85% HRR.
    """
    if distance_km <= _SHORT_RACE_KM:
        return _SHORT_RACE_HR_RATIO
    if distance_km <= _MEDIUM_RACE_KM:
        return _MEDIUM_RACE_HR_RATIO
    if distance_km <= _LONG_RACE_KM:
        return _LONG_RACE_HR_RATIO
    return _ULTRA_RACE_HR_RATIO


class EffortTier(StrEnum):
    """Intensity tier of a candidate race effort."""

    RACE = "race"
    HARD = "hard"
    MODERATE = "moderate"
    EASY = "easy"
    UNKNOWN = "unknown"


class EffortSource(StrEnum):
    """Whether an effort was detected in training or supplied by the user."""

    TRAINING = "training"
    MANUAL = "manual"


class PredictionModel(StrEnum):
    """Model requested or actually used for the prediction."""

    AUTO = "auto"
    RIEGEL = "riegel"
    CRITICAL_SPEED = "critical_speed"
    HR_EXTRAPOLATION = "hr_extrapolation"
    NONE = "none"


class Confidence(StrEnum):
    """Confidence of the race prediction."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True)
class Effort:
    """A best-effort segment used as a race-prediction reference."""

    distance_km: float
    time_s: float
    day: date
    avg_hr: float | None
    relative_hr: float | None
    efficiency: float | None
    tier: EffortTier
    source: EffortSource = EffortSource.TRAINING
    fitness_factor: float = 1.0

    @property
    def adjusted_time_s(self) -> float:
        """Return the effort time adjusted to the current fitness level."""
        factor = min(_FITNESS_FACTOR_MAX, max(_FITNESS_FACTOR_MIN, self.fitness_factor))
        return float(self.time_s * factor ** (-_FITNESS_ALPHA))

    def race_hr_ratio(self) -> float:
        """Return the target race-level heart-rate reserve for this distance."""
        return race_hr_ratio_for_distance(self.distance_km)

    def hr_correction(self, hr_rest: float, hr_max: float) -> float:
        """Return the speed multiplier from the effort HR to race-level HRR.

        A hard effort at 80% HRR is slower than a race effort at 88% HRR. Assuming
        a constant efficiency factor, the speed scales with heart rate, capped to
        avoid over-optimistic extrapolations.
        """
        if hr_max <= hr_rest or self.tier is EffortTier.RACE:
            return 1.0
        hr = self.avg_hr
        if hr is None and self.relative_hr is not None:
            hr = hr_rest + self.relative_hr * (hr_max - hr_rest)
        if hr is None or hr <= 0.0:
            return 1.0
        race_hr = hr_rest + race_hr_ratio_for_distance(self.distance_km) * (hr_max - hr_rest)
        return min(_MAX_HR_CORRECTION, max(_MIN_HR_CORRECTION, race_hr / hr))

    def race_equivalent_time_s(self, hr_rest: float, hr_max: float) -> float:
        """Return the effort time extrapolated to race-level heart rate."""
        return self.adjusted_time_s / self.hr_correction(hr_rest, hr_max)


@dataclass(frozen=True)
class CriticalSpeedFit:
    """Critical-speed model fitted to quality efforts."""

    cs_mps: float
    d_prime_m: float
    r_squared: float
    standard_error_mps: float
    efforts: tuple[Effort, ...]


@dataclass(frozen=True)
class RacePrediction:
    """Race time prediction with its support range and confidence."""

    distance_km: float
    predicted_time_s: float | None
    predicted_pace_s_per_km: float | None
    fast_time_s: float | None
    slow_time_s: float | None
    model: PredictionModel
    confidence: Confidence
    efforts: list[Effort]
    notes: list[str]


def classify_effort(relative_hr: float | None) -> EffortTier:
    """Classify an effort by its relative heart-rate reserve.

    Args:
        relative_hr: ``(HR - HR_rest) / (HR_max - HR_rest)`` or ``None``.

    Returns:
        The intensity tier; ``UNKNOWN`` when heart rate is unavailable.
    """
    if relative_hr is None:
        return EffortTier.UNKNOWN
    if relative_hr >= RACE_HR_RATIO:
        return EffortTier.RACE
    if relative_hr >= HARD_HR_RATIO:
        return EffortTier.HARD
    if relative_hr >= MODERATE_HR_RATIO:
        return EffortTier.MODERATE
    return EffortTier.EASY


def best_effort(
    samples: Sequence[SampleLike],
    distance_m: float,
    day: date,
    *,
    hr_rest: float,
    hr_max: float,
    source: EffortSource = EffortSource.TRAINING,
) -> Effort | None:
    """Return the fastest segment covering ``distance_m`` in one activity.

    Args:
        samples: Second-by-second telemetry of one running activity.
        distance_m: Target segment distance in metres.
        day: Calendar date of the activity.
        hr_rest: Resting heart rate (bpm).
        hr_max: Maximum heart rate (bpm).
        source: Whether the effort is detected or user-supplied.

    Returns:
        The fastest effort covering the distance, or ``None`` when the activity
        is shorter than the target or has no usable telemetry.

    Raises:
        ValueError: If ``distance_m`` is not positive or ``hr_max <= hr_rest``.
    """
    if distance_m <= 0.0:
        raise ValueError("distance_m must be positive")
    if hr_max <= hr_rest:
        raise ValueError("hr_max must be greater than hr_rest")

    points = _monotonic_points(samples)
    if len(points) < _MIN_POINTS:
        return None

    best: tuple[float, int, int] | None = None
    end = 0
    for start in range(len(points)):
        end = max(end, start)
        while end < len(points) and points[end][0] - points[start][0] < distance_m:
            end += 1
        if end >= len(points):
            break
        elapsed = points[end][1] - points[start][1]
        if elapsed <= 0.0:
            continue
        if best is None or elapsed < best[0]:
            best = (elapsed, start, end)
    if best is None:
        return None

    _, start, end = best
    covered = points[end][0] - points[start][0]
    elapsed = points[end][1] - points[start][1]
    if covered <= 0.0 or elapsed <= 0.0:
        return None
    speed = covered / elapsed
    time_s = distance_m / speed
    hrs = [hr for _, _, hr in points[start : end + 1] if hr is not None and hr > 0]
    avg_hr = float(np.mean(hrs)) if hrs else None
    relative_hr = (avg_hr - hr_rest) / (hr_max - hr_rest) if avg_hr is not None else None
    efficiency = speed / avg_hr if avg_hr is not None and avg_hr > 0.0 else None
    return Effort(
        distance_km=distance_m / _METERS_PER_KM,
        time_s=time_s,
        day=day,
        avg_hr=avg_hr,
        relative_hr=relative_hr,
        efficiency=efficiency,
        tier=classify_effort(relative_hr),
        source=source,
    )


def select_best_efforts(
    sessions: Sequence[tuple[date, Sequence[SampleLike]]],
    distances_km: Sequence[float],
    *,
    hr_rest: float,
    hr_max: float,
) -> list[Effort]:
    """Return the fastest detected effort for each requested distance.

    Args:
        sessions: ``(date, samples)`` pairs for running activities.
        distances_km: Distances to evaluate, in kilometres.
        hr_rest: Resting heart rate (bpm).
        hr_max: Maximum heart rate (bpm).

    Returns:
        One effort per distance that appears with enough telemetry, sorted by
        distance.
    """
    best: dict[float, Effort] = {}
    for day, samples in sessions:
        for distance_km in distances_km:
            effort = best_effort(
                samples,
                distance_km * _METERS_PER_KM,
                day,
                hr_rest=hr_rest,
                hr_max=hr_max,
            )
            if effort is None:
                continue
            current = best.get(distance_km)
            if current is None or effort.time_s < current.time_s:
                best[distance_km] = effort
    return [best[distance_km] for distance_km in sorted(best)]


def fit_critical_speed(
    efforts: Sequence[Effort],
    *,
    hr_rest: float,
    hr_max: float,
) -> CriticalSpeedFit | None:
    """Fit ``D = CS * T + D'`` to the quality efforts.

    Args:
        efforts: Candidate efforts; only ``race`` and ``hard`` tiers are used.
        hr_rest: Resting heart rate (bpm), used to normalise effort intensity.
        hr_max: Maximum heart rate (bpm), used to normalise effort intensity.

    Returns:
        The fitted model, or ``None`` when there are not enough quality efforts,
        the distances do not span enough, or the fit is not physiological.
    """
    usable = [
        effort
        for effort in efforts
        if effort.tier in (EffortTier.RACE, EffortTier.HARD)
        and effort.time_s > 0.0
        and effort.distance_km > 0.0
    ]
    if len(usable) < _MIN_CS_EFFORTS:
        return None
    times = np.array(
        [effort.race_equivalent_time_s(hr_rest, hr_max) for effort in usable],
        dtype=float,
    )
    distances = np.array([effort.distance_km * _METERS_PER_KM for effort in usable], dtype=float)
    if len(set(np.round(distances, 3))) < _MIN_CS_EFFORTS:
        return None
    if float(times.max() / times.min()) < _MIN_TIME_RATIO:
        return None

    slope, intercept = np.polyfit(times, distances, 1)
    cs_mps = float(slope)
    d_prime_m = float(intercept)
    if cs_mps <= 0.0 or d_prime_m < 0.0:
        return None
    predicted = cs_mps * times + d_prime_m
    ss_res = float(np.sum((distances - predicted) ** 2))
    ss_tot = float(np.sum((distances - np.mean(distances)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0
    return CriticalSpeedFit(
        cs_mps=cs_mps,
        d_prime_m=d_prime_m,
        r_squared=r_squared,
        standard_error_mps=_slope_standard_error(times, distances, cs_mps, d_prime_m),
        efforts=tuple(usable),
    )


def riegel_time(
    reference_distance_km: float,
    reference_time_s: float,
    target_distance_km: float,
    exponent: float = _DEFAULT_EXPONENT,
) -> float:
    """Predict a race time with Riegel's power law.

    Args:
        reference_distance_km: Distance of the reference effort.
        reference_time_s: Time of the reference effort.
        target_distance_km: Target race distance.
        exponent: Riegel exponent (typically 1.06-1.08).

    Returns:
        The predicted time in seconds.

    Raises:
        ValueError: If any distance/time is not positive or the exponent is not
            within a sensible range.
    """
    if reference_distance_km <= 0.0 or reference_time_s <= 0.0:
        raise ValueError("reference distance and time must be positive")
    if target_distance_km <= 0.0:
        raise ValueError("target distance must be positive")
    if not _MIN_EXPONENT <= exponent <= _MAX_EXPONENT:
        raise ValueError("exponent must be between 0.5 and 1.5")
    return float(reference_time_s * (target_distance_km / reference_distance_km) ** exponent)


def predict_race(
    target_distance_km: float,
    efforts: Sequence[Effort],
    *,
    model: PredictionModel = PredictionModel.AUTO,
    reference: Effort | None = None,
    exponent: float = _DEFAULT_EXPONENT,
    hr_rest: float,
    hr_max: float,
) -> RacePrediction:
    """Predict a race time from detected and/or manual efforts.

    Args:
        target_distance_km: Target race distance.
        efforts: Detected training efforts.
        model: Requested model; ``AUTO`` chooses critical speed when possible,
            then Riegel, then HR extrapolation.
        reference: Optional user-provided race/test effort.
        exponent: Riegel exponent.
        hr_rest: Resting heart rate (bpm), used by the HR extrapolation.
        hr_max: Maximum heart rate (bpm), used by the HR extrapolation.

    Returns:
        The race prediction, including the support range and confidence.

    Raises:
        ValueError: If ``target_distance_km`` is not positive.
    """
    if target_distance_km <= 0.0:
        raise ValueError("target_distance_km must be positive")
    pool = ([reference] if reference is not None else []) + list(efforts)
    if model is PredictionModel.CRITICAL_SPEED:
        return _critical_speed_prediction(target_distance_km, pool, hr_rest=hr_rest, hr_max=hr_max)
    if model is PredictionModel.RIEGEL:
        return _riegel_prediction(
            target_distance_km,
            pool,
            reference,
            exponent,
            hr_rest=hr_rest,
            hr_max=hr_max,
        )
    if model is PredictionModel.HR_EXTRAPOLATION:
        return _hr_extrapolation(target_distance_km, pool, hr_rest, hr_max)
    return _automatic_prediction(
        target_distance_km,
        pool,
        reference=reference,
        exponent=exponent,
        hr_rest=hr_rest,
        hr_max=hr_max,
    )


def _automatic_prediction(
    target_distance_km: float,
    efforts: list[Effort],
    *,
    reference: Effort | None,
    exponent: float,
    hr_rest: float,
    hr_max: float,
) -> RacePrediction:
    fit = fit_critical_speed(efforts, hr_rest=hr_rest, hr_max=hr_max)
    if (
        fit is not None
        and fit.r_squared >= _MIN_CS_R_SQUARED
        and len(fit.efforts) >= _MIN_QUALITY_EFFORTS
    ):
        return _critical_speed_prediction(
            target_distance_km, efforts, hr_rest=hr_rest, hr_max=hr_max
        )
    quality = [effort for effort in efforts if effort.tier in (EffortTier.RACE, EffortTier.HARD)]
    if quality:
        riegel = _riegel_prediction(
            target_distance_km,
            efforts,
            reference,
            exponent,
            hr_rest=hr_rest,
            hr_max=hr_max,
        )
        if riegel.model is PredictionModel.RIEGEL:
            return riegel
    return _hr_extrapolation(target_distance_km, efforts, hr_rest, hr_max)


def _critical_speed_prediction(
    target_distance_km: float,
    efforts: Sequence[Effort],
    *,
    hr_rest: float,
    hr_max: float,
) -> RacePrediction:
    fit = fit_critical_speed(efforts, hr_rest=hr_rest, hr_max=hr_max)
    if fit is None:
        return _none(
            target_distance_km,
            list(efforts),
            "Not enough race/hard efforts at different distances for critical speed.",
        )
    target_m = target_distance_km * _METERS_PER_KM
    if target_m <= fit.d_prime_m:
        return _none(
            target_distance_km,
            list(efforts),
            "Target distance is shorter than the anaerobic reserve D'.",
        )
    central = (target_m - fit.d_prime_m) / fit.cs_mps
    uncertainty = max(fit.standard_error_mps, fit.cs_mps * _CS_RANGE)
    fast = (target_m - fit.d_prime_m) / (fit.cs_mps + uncertainty)
    slow = (target_m - fit.d_prime_m) / max(fit.cs_mps - uncertainty, 1e-6)
    fast, slow = min(fast, slow), max(fast, slow)
    confidence = (
        Confidence.HIGH
        if fit.r_squared >= _HIGH_CS_R_SQUARED
        else Confidence.MEDIUM
        if fit.r_squared >= _MIN_CS_R_SQUARED
        else Confidence.LOW
    )
    notes = [
        f"Critical speed model: CS={fit.cs_mps:.2f} m/s, D'={fit.d_prime_m:.0f} m, "
        f"R²={fit.r_squared:.2f}.",
        f"Fitted on {len(fit.efforts)} quality effort(s) at different distances.",
    ]
    corrections = [effort.hr_correction(hr_rest, hr_max) for effort in fit.efforts]
    if max(corrections) > 1.0 + _FITNESS_EPS:
        notes.append(f"Efforts HR-adjusted to race effort (up to x{max(corrections):.2f} speed).")
    return _prediction(
        target_distance_km,
        central,
        fast=fast,
        slow=slow,
        model=PredictionModel.CRITICAL_SPEED,
        confidence=confidence,
        efforts=list(efforts),
        notes=notes,
    )


def _riegel_prediction(
    target_distance_km: float,
    efforts: Sequence[Effort],
    reference: Effort | None,
    exponent: float,
    *,
    hr_rest: float,
    hr_max: float,
) -> RacePrediction:
    chosen = _select_reference(target_distance_km, efforts, reference)
    if chosen is None:
        return _none(
            target_distance_km,
            list(efforts),
            "No usable reference effort for the Riegel model.",
        )
    adjusted = chosen.race_equivalent_time_s(hr_rest, hr_max)
    fast = riegel_time(chosen.distance_km, adjusted, target_distance_km, _DEFAULT_EXPONENT)
    slow = riegel_time(chosen.distance_km, adjusted, target_distance_km, _SLOW_EXPONENT)
    fast, slow = min(fast, slow), max(fast, slow)
    central = min(
        slow, max(fast, riegel_time(chosen.distance_km, adjusted, target_distance_km, exponent))
    )
    slow *= _tier_slow_penalty(chosen.tier)
    tier_range = _tier_range(chosen.tier)
    fast = min(fast, central * (1.0 - tier_range))
    slow = max(slow, central * (1.0 + tier_range))
    confidence = _reference_confidence(chosen, target_distance_km)
    notes = [_describe_effort(chosen, "Reference effort")]
    correction = chosen.hr_correction(hr_rest, hr_max)
    if correction > 1.0 + _FITNESS_EPS:
        notes.append(
            f"HR-adjusted to {chosen.race_hr_ratio():.0%} HRR race effort "
            f"(x{correction:.2f} speed)."
        )
    if abs(chosen.fitness_factor - 1.0) > _FITNESS_EPS:
        notes.append(f"Time adjusted to current fitness (factor {chosen.fitness_factor:.2f}).")
    if chosen.tier in (EffortTier.MODERATE, EffortTier.EASY):
        notes.append("The reference is not a race effort; the estimate is conservative.")
    return _prediction(
        target_distance_km,
        central,
        fast=fast,
        slow=slow,
        model=PredictionModel.RIEGEL,
        confidence=confidence,
        efforts=list(efforts),
        notes=notes,
    )


def _hr_extrapolation(
    target_distance_km: float,
    efforts: Sequence[Effort],
    hr_rest: float,
    hr_max: float,
) -> RacePrediction:
    efficiencies = [
        effort.efficiency
        for effort in efforts
        if effort.efficiency is not None and effort.efficiency > 0.0
    ]
    if not efficiencies or hr_max <= hr_rest:
        return _none(
            target_distance_km,
            list(efforts),
            "No heart-rate/efficiency data to extrapolate a race effort.",
        )
    race_ratio = race_hr_ratio_for_distance(target_distance_km)
    race_hr = hr_rest + race_ratio * (hr_max - hr_rest)
    speed = max(efficiencies) * race_hr
    if speed <= 0.0:
        return _none(
            target_distance_km,
            list(efforts),
            "Efficiency extrapolation produced a non-positive speed.",
        )
    central = target_distance_km * _METERS_PER_KM / speed
    fast = central * (1.0 - _LOW_CONFIDENCE_RANGE)
    slow = central * (1.0 + _LOW_CONFIDENCE_RANGE)
    notes = [
        "No race/hard effort available; extrapolated from easy efforts using "
        f"efficiency and {race_ratio:.0%} HRR.",
        "Low confidence: a real test or race would anchor the prediction.",
    ]
    return _prediction(
        target_distance_km,
        central,
        fast=fast,
        slow=slow,
        model=PredictionModel.HR_EXTRAPOLATION,
        confidence=Confidence.LOW,
        efforts=list(efforts),
        notes=notes,
    )


def _select_reference(
    target_distance_km: float,
    efforts: Sequence[Effort],
    reference: Effort | None,
) -> Effort | None:
    if reference is not None:
        return reference
    quality = [effort for effort in efforts if effort.tier in (EffortTier.RACE, EffortTier.HARD)]
    pool = quality or list(efforts)
    if not pool:
        return None
    return min(
        pool,
        key=lambda effort: abs(math.log(effort.distance_km / target_distance_km)),
    )


def _reference_confidence(effort: Effort, target_distance_km: float) -> Confidence:
    ratio = max(effort.distance_km, target_distance_km) / min(
        effort.distance_km, target_distance_km
    )
    if effort.tier is EffortTier.RACE and ratio <= _HIGH_CONFIDENCE_RATIO:
        return Confidence.HIGH
    if effort.tier is EffortTier.HARD and ratio <= _MEDIUM_CONFIDENCE_RATIO:
        return Confidence.MEDIUM
    return Confidence.LOW


def _tier_slow_penalty(tier: EffortTier) -> float:
    if tier is EffortTier.EASY:
        return _EASY_SLOW_PENALTY
    if tier is EffortTier.MODERATE:
        return _MODERATE_SLOW_PENALTY
    return 1.0


def _tier_range(tier: EffortTier) -> float:
    if tier is EffortTier.EASY:
        return _EASY_RANGE
    if tier is EffortTier.MODERATE:
        return _MODERATE_RANGE
    if tier is EffortTier.HARD:
        return _HARD_RANGE
    return 0.0


def _describe_effort(effort: Effort, prefix: str) -> str:
    hr = "HR n/a" if effort.relative_hr is None else f"{effort.relative_hr:.0%} HRR"
    source = "manual" if effort.source is EffortSource.MANUAL else "training"
    return (
        f"{prefix}: {effort.distance_km:.2f} km in {format_duration(effort.time_s)} "
        f"on {effort.day.isoformat()} ({hr}, {source})."
    )


def format_duration(seconds: float) -> str:
    """Format seconds as ``H:MM:SS`` (or ``MM:SS`` under one hour)."""
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _prediction(
    distance_km: float,
    central: float,
    *,
    fast: float,
    slow: float,
    model: PredictionModel,
    confidence: Confidence,
    efforts: list[Effort],
    notes: list[str],
) -> RacePrediction:
    pace = central / distance_km
    return RacePrediction(
        distance_km=distance_km,
        predicted_time_s=central,
        predicted_pace_s_per_km=pace,
        fast_time_s=fast,
        slow_time_s=slow,
        model=model,
        confidence=confidence,
        efforts=efforts,
        notes=notes,
    )


def _none(
    distance_km: float,
    efforts: list[Effort],
    note: str,
) -> RacePrediction:
    return RacePrediction(
        distance_km=distance_km,
        predicted_time_s=None,
        predicted_pace_s_per_km=None,
        fast_time_s=None,
        slow_time_s=None,
        model=PredictionModel.NONE,
        confidence=Confidence.NONE,
        efforts=efforts,
        notes=[note],
    )


def _monotonic_points(
    samples: Sequence[SampleLike],
) -> list[tuple[float, float, int | None]]:
    """Return ``(distance_m, elapsed_s, hr)`` points with non-decreasing distance."""
    ordered = sorted(
        (sample for sample in samples if sample.is_valid and sample.distance_m is not None),
        key=lambda sample: float(sample.elapsed_s),
    )
    points: list[tuple[float, float, int | None]] = []
    last_distance = -math.inf
    for sample in ordered:
        distance = float(sample.distance_m) if sample.distance_m is not None else 0.0
        if distance < last_distance:
            continue
        points.append((distance, float(sample.elapsed_s), sample.hr))
        last_distance = distance
    return points


def _slope_standard_error(
    times: np.ndarray,
    distances: np.ndarray,
    cs_mps: float,
    d_prime_m: float,
) -> float:
    dof = len(times) - 2
    if dof <= 0:
        return 0.0
    residuals = distances - (cs_mps * times + d_prime_m)
    s_err = math.sqrt(float(np.sum(residuals**2)) / dof)
    denominator = float(np.sum((times - np.mean(times)) ** 2))
    if denominator <= 0.0:
        return 0.0
    return s_err / math.sqrt(denominator)
