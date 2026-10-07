"""Unit tests for the Foster session-RPE load."""

from __future__ import annotations

import pytest

from athlete_stress_sim.core.metrics.rpe import session_rpe_load


def test_load_is_rpe_times_minutes() -> None:
    assert session_rpe_load(5.0, 1800.0) == pytest.approx(150.0)


def test_upper_bound_rpe() -> None:
    assert session_rpe_load(10.0, 60.0) == pytest.approx(10.0)


def test_zero_rpe_is_zero_load() -> None:
    assert session_rpe_load(0.0, 3600.0) == 0.0


def test_rejects_rpe_above_range() -> None:
    with pytest.raises(ValueError, match="rpe"):
        session_rpe_load(11.0, 600.0)


def test_rejects_negative_rpe() -> None:
    with pytest.raises(ValueError, match="rpe"):
        session_rpe_load(-1.0, 600.0)


def test_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="duration_s"):
        session_rpe_load(5.0, -1.0)
