"""Unit tests for the race-aware tapering helpers (``S14``, ``RF-05.2``)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from athlete_stress_sim.core.metrics.load import daily_load_series, planned_session_load
from athlete_stress_sim.core.metrics.taper import (
    build_taper_sessions,
    running_baseline,
    taper_weekly_factors,
)
from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response

_REFERENCE = date(2026, 12, 14)


def _sessions(
    *, count: int = 8, distance_km: float = 10.0, duration_s: float = 3000.0
) -> list[tuple[date, float, float | None, float | None]]:
    return [
        (_REFERENCE - timedelta(days=27) + timedelta(days=3 * index), distance_km, duration_s, 6.0)
        for index in range(count)
    ]


def test_running_baseline_estimates_weekly_volume() -> None:
    baseline = running_baseline(_sessions(), reference_date=_REFERENCE)

    assert baseline is not None
    assert baseline.weekly_km == pytest.approx(20.0)
    assert baseline.runs_per_week == 2
    assert baseline.pace_min_per_km == pytest.approx(5.0)
    assert baseline.rpe == pytest.approx(6.0)
    assert baseline.sessions == 8
    assert baseline.weeks == 4


def test_running_baseline_requires_enough_sessions() -> None:
    assert running_baseline(_sessions(count=3), reference_date=_REFERENCE) is None


def test_running_baseline_ignores_sessions_outside_window() -> None:
    old = [(_REFERENCE - timedelta(days=60 + index), 10.0, 3000.0, 6.0) for index in range(8)]

    assert running_baseline(old, reference_date=_REFERENCE) is None


def test_running_baseline_uses_default_rpe_without_session_rpe() -> None:
    sessions = [(day, distance, duration, None) for day, distance, duration, _ in _sessions()]

    baseline = running_baseline(sessions, reference_date=_REFERENCE, default_rpe=7.0)

    assert baseline is not None
    assert baseline.rpe == pytest.approx(7.0)


def test_running_baseline_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        running_baseline(_sessions(), reference_date=_REFERENCE, weeks=0)


def test_taper_weekly_factors_decrease_linearly() -> None:
    factors = taper_weekly_factors(3)

    assert factors == pytest.approx([0.75, 0.55, 0.35])
    assert taper_weekly_factors(1) == pytest.approx([0.5])
    with pytest.raises(ValueError):
        taper_weekly_factors(0)


def test_build_taper_sessions_reduces_volume_week_by_week() -> None:
    sessions, weeks = build_taper_sessions(
        race_date=date(2026, 12, 13),
        base_weekly_km=40.0,
        pace_min_per_km=5.5,
        runs_per_week=3,
        rpe=6.0,
        taper_weeks=3,
    )

    assert len(sessions) == 8
    assert [week.factor for week in weeks] == pytest.approx([0.75, 0.55, 0.35])
    assert [week.distance_km for week in weeks] == pytest.approx([30.0, 22.0, 14.0])
    assert [week.sessions for week in weeks] == [3, 3, 2]
    assert all(session.date < date(2026, 12, 13) for session in sessions)
    assert all(session.pace_min_per_km == pytest.approx(5.5) for session in sessions)
    assert all(session.rpe == pytest.approx(6.0) for session in sessions)


def test_build_taper_sessions_handles_race_at_week_start() -> None:
    sessions, weeks = build_taper_sessions(
        race_date=date(2026, 12, 14),
        base_weekly_km=40.0,
        pace_min_per_km=5.5,
        taper_weeks=1,
    )

    assert sessions == []
    assert weeks[0].sessions == 0
    assert weeks[0].distance_km == pytest.approx(0.0)


def test_taper_lifts_freshness_into_race_day() -> None:
    race_date = date(2026, 12, 13)
    params = BanisterParams(p0=0.0, k1=1.0, k2=2.0, tau1=42.0, tau2=7.0)
    sessions, _ = build_taper_sessions(
        race_date=race_date,
        base_weekly_km=40.0,
        pace_min_per_km=5.0,
        rpe=6.0,
        taper_weeks=3,
    )
    taper_start = min(session.date for session in sessions)
    history: list[tuple[date, float]] = []
    day = taper_start - timedelta(weeks=8)
    while day < taper_start:
        if day.weekday() in (0, 2, 4):
            history.append((day, 300.0))
        day += timedelta(days=1)
    planned = [
        (session.date, planned_session_load(session.distance_km, session.pace_min_per_km, 6.0))
        for session in sessions
    ]
    dates, loads = daily_load_series([*history, *planned, (race_date, 0.0)])
    result = impulse_response(loads, params)
    start_index = dates.index(taper_start)
    race_index = dates.index(race_date)

    assert result.freshness[race_index] > result.freshness[start_index]
    assert result.fitness[race_index] > 0.85 * result.fitness[start_index]
    peak_index = max(range(len(dates)), key=lambda index: result.freshness[index])
    assert dates[peak_index] == race_date


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"base_weekly_km": 0.0},
        {"pace_min_per_km": 0.0},
        {"runs_per_week": 0},
        {"runs_per_week": 8},
        {"rpe": -1.0},
        {"rpe": 11.0},
        {"taper_weeks": 0},
    ],
)
def test_build_taper_sessions_rejects_invalid_inputs(overrides: dict[str, float]) -> None:
    arguments: dict[str, float] = {
        "base_weekly_km": 40.0,
        "pace_min_per_km": 5.5,
        "runs_per_week": 3,
        "rpe": 6.0,
        "taper_weeks": 3,
        **overrides,
    }

    with pytest.raises(ValueError):
        build_taper_sessions(race_date=date(2026, 12, 13), **arguments)
