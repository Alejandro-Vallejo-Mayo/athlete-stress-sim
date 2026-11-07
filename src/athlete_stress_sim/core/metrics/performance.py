"""Observed running performance for the Banister EKF (``RF-03.2``).

The extended Kalman filter (``core.models.ekf``) tunes the individual Banister
parameters from observed performance. ``RF-03.2`` defines that observation as
pace at a constant heart rate; this module approximates it with the session-level
efficiency factor ``EF = speed / HR`` (the same quantity the aerobic-decoupling
metric uses per kilometre, ``RF-05.3``). A higher EF means more speed at the same
heart rate, so a higher EF is better performance.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from athlete_stress_sim.core.etl.types import Sample
from athlete_stress_sim.core.metrics.decoupling import efficiency_factor


def session_efficiency(samples: Sequence[Sample]) -> float | None:
    """Return the mean efficiency factor ``speed / HR`` of a running session.

    Args:
        samples: Second-by-second telemetry of one running session.

    Returns:
        The mean EF over the valid samples (``speed > 0`` and ``hr > 0``), or
        ``None`` when no sample has a usable speed and heart rate.
    """
    total = 0.0
    count = 0
    for sample in samples:
        factor = efficiency_factor(sample.speed_mps, sample.hr)
        if factor is None:
            continue
        total += factor
        count += 1
    if count == 0:
        return None
    return total / count


def performance_observations(
    dates: Sequence[date],
    sessions: Iterable[tuple[date, float | None]],
) -> dict[int, float]:
    """Map dated running efficiencies to indices of the daily load series.

    Several sessions on the same day are averaged; sessions without a valid
    efficiency or outside ``dates`` are ignored. Only running sessions provide an
    observation, because strength sessions have no speed and therefore no EF.

    Args:
        dates: Contiguous daily dates returned by :func:`daily_load_series`.
        sessions: ``(date, efficiency)`` pairs, where efficiency is ``None`` when
            the session has no usable telemetry.

    Returns:
        A mapping from day index in ``dates`` to the mean observed EF.
    """
    index_by_date = {day: index for index, day in enumerate(dates)}
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for day, value in sessions:
        if value is None:
            continue
        index = index_by_date.get(day)
        if index is None:
            continue
        totals[index] = totals.get(index, 0.0) + value
        counts[index] = counts.get(index, 0) + 1
    return {index: totals[index] / counts[index] for index in sorted(totals)}
