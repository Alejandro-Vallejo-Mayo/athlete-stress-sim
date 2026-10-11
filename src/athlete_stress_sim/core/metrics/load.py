"""Training-load assembly: per-session load and the daily load series.

Bridges the running TRIMP (Banister) and gym session-RPE metrics into a single
internal-load series that feeds the ACWR (S7) and the Banister model (S8).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from athlete_stress_sim.core.etl.sports import is_strength
from athlete_stress_sim.core.metrics.rpe import session_rpe_load
from athlete_stress_sim.core.metrics.trimp import Sex, trimp_from_samples

_SECONDS_PER_MINUTE = 60.0


def session_load(
    sport: str,
    sub_sport: str,
    *,
    hr_samples: Sequence[float | None] | None = None,
    duration_s: float | None = None,
    rpe: float | None = None,
    hr_rest: float,
    hr_max: float,
    sex: Sex,
) -> float | None:
    """Compute one session's internal load.

    Strength sessions use the session-RPE load (requires ``rpe`` and
    ``duration_s``); endurance sessions use the Banister TRIMP integrated over
    ``hr_samples``. Sessions without the required inputs return ``None``.

    Args:
        sport: FIT sport value.
        sub_sport: FIT sub-sport value.
        hr_samples: Per-second heart-rate samples (endurance sessions).
        duration_s: Session duration in seconds (strength sessions).
        rpe: Session-RPE on the Borg CR-10 scale (strength sessions).
        hr_rest: Resting heart rate (bpm).
        hr_max: Maximum heart rate (bpm).
        sex: Selects the Banister TRIMP coefficients.

    Returns:
        The session load in arbitrary units, or ``None`` if it cannot be computed.
    """
    if is_strength(sport, sub_sport):
        if rpe is None or duration_s is None:
            return None
        return session_rpe_load(rpe, duration_s)
    if hr_samples:
        return trimp_from_samples(hr_samples, hr_rest, hr_max, sex)
    return None


def planned_session_load(distance_km: float, pace_min_per_km: float, rpe: float) -> float:
    """Estimate a planned running session's load from distance, pace and RPE.

    The duration is derived as ``distance_km * pace_min_per_km`` and the load
    uses Foster's session-RPE (``rpe * duration_min``), keeping projected loads
    on the same arbitrary-unit scale as the recorded TRIMP/sRPE (``RF-05.2``).

    Args:
        distance_km: Planned distance in kilometres.
        pace_min_per_km: Planned pace in minutes per kilometre.
        rpe: Planned session RPE on the Borg CR-10 scale (0-10).

    Returns:
        The session load in arbitrary units.

    Raises:
        ValueError: If ``distance_km`` or ``pace_min_per_km`` is not positive.
    """
    if distance_km <= 0.0:
        raise ValueError("distance_km must be positive")
    if pace_min_per_km <= 0.0:
        raise ValueError("pace_min_per_km must be positive")
    duration_s = distance_km * pace_min_per_km * _SECONDS_PER_MINUTE
    return session_rpe_load(rpe, duration_s)


def daily_load_series(
    loads: Iterable[tuple[date, float]],
) -> tuple[list[date], list[float]]:
    """Aggregate dated session loads into a contiguous daily series.

    Rest days are filled with ``0.0`` so the EWMA can decay across them.

    Args:
        loads: ``(date, load)`` pairs; several sessions on the same day are summed.

    Returns:
        A ``(dates, daily_totals)`` tuple covering every day between the first
        and last dates. Both lists are empty when ``loads`` is empty.
    """
    totals: dict[date, float] = {}
    for day, load in loads:
        totals[day] = totals.get(day, 0.0) + load
    if not totals:
        return [], []

    first, last = min(totals), max(totals)
    days: list[date] = []
    values: list[float] = []
    current = first
    while current <= last:
        days.append(current)
        values.append(totals.get(current, 0.0))
        current += timedelta(days=1)
    return days, values
