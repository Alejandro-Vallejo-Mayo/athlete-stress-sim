"""Banister TRIMP (training impulse) for running sessions.

Implements Banister's exponential weighting factor ``y = a * exp(b * HR_r)``,
with sex-specific coefficients ``(a, b)``, and offers both a closed form based
on average heart rate and a per-second integral over stored samples.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import StrEnum

_SECONDS_PER_MINUTE = 60.0

# Banister weighting-factor coefficients (Morton et al., 1990).
_MALE_COEFFICIENTS = (0.64, 1.92)
_FEMALE_COEFFICIENTS = (0.86, 1.67)


class Sex(StrEnum):
    """Biological sex, selecting the Banister TRIMP coefficients."""

    MALE = "male"
    FEMALE = "female"


def trimp_coefficients(sex: Sex) -> tuple[float, float]:
    """Return the ``(a, b)`` Banister weighting coefficients for ``sex``."""
    if sex is Sex.FEMALE:
        return _FEMALE_COEFFICIENTS
    return _MALE_COEFFICIENTS


def heart_rate_reserve(hr: float, hr_rest: float, hr_max: float) -> float:
    """Fractional heart-rate reserve, clamped to ``[0, 1]``.

    Args:
        hr: Heart rate sample in bpm.
        hr_rest: Resting heart rate in bpm.
        hr_max: Maximum heart rate in bpm.

    Returns:
        ``(hr - hr_rest) / (hr_max - hr_rest)`` clamped to ``[0, 1]``.

    Raises:
        ValueError: If ``hr_max`` is not greater than ``hr_rest``.
    """
    if hr_max <= hr_rest:
        raise ValueError("hr_max must be greater than hr_rest")
    ratio = (hr - hr_rest) / (hr_max - hr_rest)
    return min(1.0, max(0.0, ratio))


def trimp_from_average(
    duration_s: float,
    hr_avg: float,
    hr_rest: float,
    hr_max: float,
    sex: Sex,
) -> float:
    """Compute TRIMP from a session's duration and average heart rate.

    Args:
        duration_s: Session duration in seconds.
        hr_avg: Average heart rate during the session (bpm).
        hr_rest: Resting heart rate (bpm).
        hr_max: Maximum heart rate (bpm).
        sex: Selects the ``(a, b)`` weighting coefficients.

    Returns:
        The session TRIMP in arbitrary units.
    """
    duration_min = duration_s / _SECONDS_PER_MINUTE
    return duration_min * _impulse_per_minute(hr_avg, hr_rest, hr_max, sex)


def trimp_from_samples(
    hrs: Iterable[float | None],
    hr_rest: float,
    hr_max: float,
    sex: Sex,
    interval_s: float = 1.0,
) -> float:
    """Integrate TRIMP over a per-sample heart-rate series.

    Samples that are ``None`` or non-positive are ignored (they contribute no
    load). The heart-rate reserve is clamped, so out-of-range values cannot
    dominate the sum.

    Args:
        hrs: Heart-rate samples (bpm), typically one per second.
        hr_rest: Resting heart rate (bpm).
        hr_max: Maximum heart rate (bpm).
        sex: Selects the ``(a, b)`` weighting coefficients.
        interval_s: Duration represented by each sample, in seconds.

    Returns:
        The integrated TRIMP in arbitrary units.

    Raises:
        ValueError: If ``interval_s`` is not positive.
    """
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    dt_min = interval_s / _SECONDS_PER_MINUTE
    total = 0.0
    for hr in hrs:
        if hr is None or hr <= 0:
            continue
        total += dt_min * _impulse_per_minute(hr, hr_rest, hr_max, sex)
    return total


def _impulse_per_minute(hr: float, hr_rest: float, hr_max: float, sex: Sex) -> float:
    a, b = trimp_coefficients(sex)
    ratio = heart_rate_reserve(hr, hr_rest, hr_max)
    return ratio * a * math.exp(b * ratio)
