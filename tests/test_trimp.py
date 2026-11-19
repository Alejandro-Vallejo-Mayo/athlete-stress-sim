"""Unit tests for the Banister TRIMP metric."""

from __future__ import annotations

import pytest

from athlete_stress_sim.core.metrics.trimp import (
    Sex,
    heart_rate_reserve,
    trimp_coefficients,
    trimp_from_average,
    trimp_from_samples,
)

_HR_MAX = 200.0
_HR_REST = 40.0


def test_trimp_coefficients_by_sex() -> None:
    assert trimp_coefficients(Sex.MALE) == (0.64, 1.92)
    assert trimp_coefficients(Sex.FEMALE) == (0.86, 1.67)


def test_heart_rate_reserve_midpoint() -> None:
    assert heart_rate_reserve(120.0, _HR_REST, _HR_MAX) == pytest.approx(0.5)


def test_heart_rate_reserve_clamps_to_unit_interval() -> None:
    assert heart_rate_reserve(10.0, _HR_REST, _HR_MAX) == 0.0
    assert heart_rate_reserve(250.0, _HR_REST, _HR_MAX) == 1.0


def test_heart_rate_reserve_requires_hr_max_greater() -> None:
    with pytest.raises(ValueError, match="hr_max"):
        heart_rate_reserve(120.0, 100.0, 100.0)


def test_trimp_from_average_male_reference() -> None:
    # 30 min (1800 s) at 130 bpm, HRmax=200, HRrest=40 -> hand-computed ~31.8025.
    value = trimp_from_average(1800.0, 130.0, _HR_REST, _HR_MAX, Sex.MALE)

    assert value == pytest.approx(31.8025, rel=1e-4)


def test_trimp_from_average_depends_on_sex() -> None:
    male = trimp_from_average(1800.0, 130.0, _HR_REST, _HR_MAX, Sex.MALE)
    female = trimp_from_average(1800.0, 130.0, _HR_REST, _HR_MAX, Sex.FEMALE)

    assert female != male


def test_integral_of_constant_hr_equals_closed_form() -> None:
    integral = trimp_from_samples([130.0] * 1800, _HR_REST, _HR_MAX, Sex.MALE)
    closed = trimp_from_average(1800.0, 130.0, _HR_REST, _HR_MAX, Sex.MALE)

    assert integral == pytest.approx(closed)


def test_integral_ignores_none_and_non_positive() -> None:
    value = trimp_from_samples([120.0, None, 0.0, -5.0, 120.0], _HR_REST, _HR_MAX, Sex.MALE)
    expected = trimp_from_samples([120.0, 120.0], _HR_REST, _HR_MAX, Sex.MALE)

    assert value == pytest.approx(expected)


def test_integral_requires_positive_interval() -> None:
    with pytest.raises(ValueError, match="interval_s"):
        trimp_from_samples([120.0], _HR_REST, _HR_MAX, Sex.MALE, interval_s=0.0)


def test_integral_scales_with_interval() -> None:
    one_second = trimp_from_samples([120.0] * 10, _HR_REST, _HR_MAX, Sex.MALE, interval_s=1.0)
    two_seconds = trimp_from_samples([120.0] * 10, _HR_REST, _HR_MAX, Sex.MALE, interval_s=2.0)

    assert two_seconds == pytest.approx(2 * one_second)
