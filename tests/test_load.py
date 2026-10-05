"""Unit tests for per-session and daily load assembly."""

from __future__ import annotations

from datetime import date

import pytest

from athlete_stress_sim.core.metrics.load import daily_load_series, session_load
from athlete_stress_sim.core.metrics.trimp import Sex

_HR_REST = 40.0
_HR_MAX = 200.0


def test_strength_session_uses_srpe() -> None:
    load = session_load(
        "training",
        "strength_training",
        rpe=6.0,
        duration_s=3600.0,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
        sex=Sex.MALE,
    )

    assert load == pytest.approx(360.0)


def test_strength_without_rpe_returns_none() -> None:
    load = session_load(
        "training",
        "strength_training",
        duration_s=3600.0,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
        sex=Sex.MALE,
    )

    assert load is None


def test_running_session_uses_trimp() -> None:
    load = session_load(
        "running",
        "street",
        hr_samples=[130.0] * 1800,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
        sex=Sex.MALE,
    )

    assert load == pytest.approx(31.8025, rel=1e-4)


def test_endurance_session_without_samples_returns_none() -> None:
    load = session_load(
        "running",
        "street",
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
        sex=Sex.MALE,
    )

    assert load is None


def test_daily_load_series_sums_same_day_and_fills_gaps() -> None:
    days, values = daily_load_series(
        [
            (date(2026, 1, 1), 100.0),
            (date(2026, 1, 1), 50.0),
            (date(2026, 1, 3), 20.0),
        ]
    )

    assert days == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    assert values == pytest.approx([150.0, 0.0, 20.0])


def test_daily_load_series_empty() -> None:
    assert daily_load_series([]) == ([], [])
