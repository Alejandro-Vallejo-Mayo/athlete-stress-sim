"""Race-aware tapering: recent running baseline and progressive taper plan (S14).

The half-marathon taper reduces weekly running volume over the last weeks while
keeping the intensity (pace and RPE) so the fitness-fatigue model can shed
fatigue faster than fitness. Both helpers are pure functions on top of the
persisted running sessions, so the API and the dashboard share the same
schedule without depending on DuckDB or Dash (``RF-05.2``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean

BASE_WINDOW_WEEKS = 4
DEFAULT_TAPER_WEEKS = 3
DEFAULT_RUNS_PER_WEEK = 3
DEFAULT_RPE = 6.0

_DAYS_PER_WEEK = 7
_SECONDS_PER_MINUTE = 60.0
_MIN_BASELINE_SESSIONS = 4
_FIRST_WEEK_FACTOR = 0.75
_LAST_WEEK_FACTOR = 0.35
_SINGLE_WEEK_FACTOR = 0.5
_MIN_DISTANCE_KM = 0.1
_MAX_RPE = 10.0
_WEEKDAY_ORDER = (1, 3, 6, 5, 2, 0, 4)


@dataclass(frozen=True)
class RunningBaseline:
    """Recent weekly running volume used as the taper starting point."""

    weekly_km: float
    runs_per_week: int
    pace_min_per_km: float
    rpe: float
    sessions: int
    weeks: int


@dataclass(frozen=True)
class TaperSession:
    """A single planned taper session."""

    date: date
    distance_km: float
    pace_min_per_km: float
    rpe: float


@dataclass(frozen=True)
class TaperWeek:
    """Weekly volume of the taper plan, oldest week first."""

    start: date
    factor: float
    distance_km: float
    sessions: int


def running_baseline(
    sessions: Sequence[tuple[date, float, float | None, float | None]],
    *,
    reference_date: date,
    weeks: int = BASE_WINDOW_WEEKS,
    default_rpe: float = DEFAULT_RPE,
) -> RunningBaseline | None:
    """Estimate the recent weekly running volume from completed sessions.

    Args:
        sessions: ``(date, distance_km, duration_s, rpe)`` tuples for running
            sessions; entries missing distance, duration or RPE are tolerated.
        reference_date: First day after the baseline window (typically the taper
            start); sessions on or after it are ignored.
        weeks: Length of the lookback window in weeks.
        default_rpe: RPE used when the window has no session RPE.

    Returns:
        The estimated baseline, or ``None`` when fewer than four valid sessions
        fall inside the window.

    Raises:
        ValueError: If ``weeks`` is not positive.
    """
    if weeks < 1:
        raise ValueError("weeks must be positive")

    window_start = reference_date - timedelta(weeks=weeks)
    valid: list[tuple[date, float, float, float | None]] = []
    for day, distance_km, duration_s, rpe in sessions:
        if not window_start <= day < reference_date:
            continue
        if distance_km <= 0.0 or duration_s is None or duration_s <= 0.0:
            continue
        valid.append((day, distance_km, duration_s, rpe))
    if len(valid) < _MIN_BASELINE_SESSIONS:
        return None

    earliest = min(day for day, *_ in valid)
    covered = max(1, min(weeks, math.ceil((reference_date - earliest).days / _DAYS_PER_WEEK)))
    total_km = sum(distance_km for _, distance_km, _, _ in valid)
    total_minutes = sum(duration_s for _, _, duration_s, _ in valid) / _SECONDS_PER_MINUTE
    rpes = [rpe for *_, rpe in valid if rpe is not None]
    return RunningBaseline(
        weekly_km=total_km / covered,
        runs_per_week=max(1, round(len(valid) / covered)),
        pace_min_per_km=total_minutes / total_km,
        rpe=fmean(rpes) if rpes else default_rpe,
        sessions=len(valid),
        weeks=covered,
    )


def taper_weekly_factors(weeks: int) -> list[float]:
    """Return the weekly volume factors of a taper, oldest week first.

    Args:
        weeks: Number of taper weeks (the last one contains the race).

    Returns:
        Factors decreasing linearly from ``0.75`` to ``0.35``; a one-week taper
        uses ``0.5``.

    Raises:
        ValueError: If ``weeks`` is not positive.
    """
    if weeks < 1:
        raise ValueError("weeks must be positive")
    if weeks == 1:
        return [_SINGLE_WEEK_FACTOR]
    step = (_LAST_WEEK_FACTOR - _FIRST_WEEK_FACTOR) / (weeks - 1)
    return [_FIRST_WEEK_FACTOR + step * index for index in range(weeks)]


def build_taper_sessions(
    *,
    race_date: date,
    base_weekly_km: float,
    pace_min_per_km: float,
    runs_per_week: int = DEFAULT_RUNS_PER_WEEK,
    rpe: float = DEFAULT_RPE,
    taper_weeks: int = DEFAULT_TAPER_WEEKS,
) -> tuple[list[TaperSession], list[TaperWeek]]:
    """Build a progressive pre-race taper plan.

    Weekly volume falls according to :func:`taper_weekly_factors` while pace and
    RPE stay constant (intensity is preserved). Sessions are placed on the
    preferred weekdays and never on or after ``race_date``, so race morning is a
    rest day in the projection.

    Args:
        race_date: Target race day.
        base_weekly_km: Current weekly running volume in kilometres.
        pace_min_per_km: Planned pace in minutes per kilometre.
        runs_per_week: Number of running sessions per week (1-7).
        rpe: Planned session RPE on the Borg CR-10 scale (0-10).
        taper_weeks: Number of taper weeks, including the race week.

    Returns:
        The planned sessions sorted by date and the weekly summaries.

    Raises:
        ValueError: If any input is outside its valid range.
    """
    if base_weekly_km <= 0.0:
        raise ValueError("base_weekly_km must be positive")
    if pace_min_per_km <= 0.0:
        raise ValueError("pace_min_per_km must be positive")
    if not 1 <= runs_per_week <= _DAYS_PER_WEEK:
        raise ValueError("runs_per_week must be between 1 and 7")
    if not 0.0 <= rpe <= _MAX_RPE:
        raise ValueError("rpe must be between 0 and 10")
    if taper_weeks < 1:
        raise ValueError("taper_weeks must be positive")

    race_week_start = race_date - timedelta(days=race_date.weekday())
    taper_start = race_week_start - timedelta(weeks=taper_weeks - 1)
    factors = taper_weekly_factors(taper_weeks)
    sessions: list[TaperSession] = []
    summaries: list[TaperWeek] = []
    for index, factor in enumerate(factors):
        week_start = taper_start + timedelta(weeks=index)
        days = sorted(
            week_start + timedelta(days=offset) for offset in _WEEKDAY_ORDER[:runs_per_week]
        )
        days = [day for day in days if day < race_date]
        if not days:
            summaries.append(TaperWeek(week_start, factor, 0.0, 0))
            continue
        distances = _split_volume(base_weekly_km * factor, len(days))
        for day, distance in zip(days, distances, strict=True):
            sessions.append(TaperSession(day, distance, pace_min_per_km, rpe))
        summaries.append(TaperWeek(week_start, factor, round(sum(distances), 1), len(distances)))
    sessions.sort(key=lambda session: session.date)
    return sessions, summaries


def _split_volume(weekly_km: float, runs: int) -> list[float]:
    """Split a weekly volume into ``runs`` equally-sized distances."""
    per_run = weekly_km / runs
    distances = [round(per_run, 1) for _ in range(runs - 1)]
    remainder = round(weekly_km - sum(distances), 1)
    distances.append(max(remainder, _MIN_DISTANCE_KM))
    return [max(distance, _MIN_DISTANCE_KM) for distance in distances]
