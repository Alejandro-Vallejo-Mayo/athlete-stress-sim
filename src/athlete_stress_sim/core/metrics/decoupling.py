"""Aerobic decoupling from running telemetry (``RF-05.3``).

The efficiency factor (EF) relates speed to heart rate: ``EF = speed / HR``
(higher is better). Computing it per kilometre and comparing the first and the
second half of a long run exposes cardiovascular drift: a positive decoupling
means EF fell in the second half (the athlete slowed at the same heart rate).
"""

from __future__ import annotations

from collections.abc import Sequence

from athlete_stress_sim.core.etl.types import Sample

_METERS_PER_KM = 1000.0
_MIN_KM_SEGMENTS = 2


def efficiency_factor(speed_mps: float | None, hr: int | None) -> float | None:
    """Return the efficiency factor ``speed / HR`` for one sample.

    Args:
        speed_mps: Instantaneous speed in metres per second.
        hr: Heart rate in bpm.

    Returns:
        ``speed / HR`` in metres per second per bpm, or ``None`` when either
        value is missing or non-positive.
    """
    if speed_mps is None or hr is None or speed_mps <= 0.0 or hr <= 0:
        return None
    return speed_mps / hr


def per_km_efficiency(samples: Sequence[Sample]) -> list[float]:
    """Compute the efficiency factor for each completed kilometre.

    Samples are binned by their cumulative ``distance_m``; the EF of a kilometre
    is ``mean(speed) / mean(HR)`` over its valid samples. Kilometres without
    valid samples are omitted.

    Args:
        samples: Second-by-second telemetry ordered by time.

    Returns:
        The EF per kilometre, ordered by ascending kilometre.
    """
    speed_sum: dict[int, float] = {}
    hr_sum: dict[int, float] = {}
    for sample in samples:
        speed = sample.speed_mps
        hr = sample.hr
        distance = sample.distance_m
        if speed is None or hr is None or distance is None or speed <= 0.0 or hr <= 0:
            continue
        km = int(distance // _METERS_PER_KM)
        speed_sum[km] = speed_sum.get(km, 0.0) + speed
        hr_sum[km] = hr_sum.get(km, 0.0) + float(hr)
    return [speed_sum[km] / hr_sum[km] for km in sorted(speed_sum) if hr_sum[km] > 0.0]


def aerobic_decoupling(samples: Sequence[Sample]) -> float | None:
    """Return the aerobic decoupling percentage of a run.

    The per-kilometre efficiency factors are split in halves; the result is the
    relative drop from the first to the second half. A positive value indicates
    the EF fell as the run progressed (cardiovascular drift).

    Args:
        samples: Second-by-second telemetry ordered by time.

    Returns:
        The decoupling percentage, or ``None`` when there are fewer than two
        kilometres with valid data.
    """
    per_km = per_km_efficiency(samples)
    if len(per_km) < _MIN_KM_SEGMENTS:
        return None
    middle = len(per_km) // 2
    first = per_km[:middle]
    second = per_km[middle:]
    first_ef = sum(first) / len(first)
    second_ef = sum(second) / len(second)
    if first_ef <= 0.0:
        return None
    return (first_ef - second_ef) / first_ef * 100.0
