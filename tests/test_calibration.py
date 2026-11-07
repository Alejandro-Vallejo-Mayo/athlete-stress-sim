"""Unit tests for Banister parameter calibration (``RF-03.2``)."""

from __future__ import annotations

import statistics

import numpy as np
import pytest

from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response
from athlete_stress_sim.core.models.calibration import calibrate_banister

_TRUE = BanisterParams(p0=1000.0, k1=1.0, k2=2.0, tau1=45.0, tau2=15.0)
_PRIOR = BanisterParams(p0=1000.0, k1=1.0, k2=2.0, tau1=42.0, tau2=12.0)


def _loads(days: int = 300) -> list[float]:
    loads: list[float] = []
    for week in range(days // 7 + 1):
        base = 80 + 40 * (week % 4)
        deload = 0.5 if week % 4 == 3 else 1.0
        loads.extend(
            [
                base * deload,
                0.0,
                base * deload * 1.2,
                base * deload * 1.4,
                0.0,
                base * deload * 1.1,
                base * deload * 0.7,
            ]
        )
    return loads[:days]


def _observations(loads: list[float]) -> dict[int, float]:
    truth = impulse_response(loads, _TRUE)
    return {day: truth.performance[day] for day in range(4, len(loads), 5)}


def test_few_observations_fall_back_to_prior() -> None:
    result = calibrate_banister([100.0] * 10, {1: 0.02, 2: 0.021, 3: 0.019}, _PRIOR)

    assert result.calibrated is False
    assert result.params == _PRIOR
    assert result.observations == 3


def test_empty_history_falls_back_to_prior() -> None:
    result = calibrate_banister([], {0: 0.02, 1: 0.02, 2: 0.02, 3: 0.02}, _PRIOR)

    assert result.calibrated is False
    assert result.params == _PRIOR


def test_constant_observations_fall_back_to_prior() -> None:
    loads = _loads()
    observations = {day: 0.02 for day in range(0, len(loads), 5)}

    result = calibrate_banister(loads, observations, _PRIOR)

    assert result.calibrated is False
    assert result.params == _PRIOR


def test_uninformative_observations_fall_back_to_prior() -> None:
    loads = _loads()
    rng = np.random.default_rng(7)
    observations = {day: float(1.0 + rng.normal(0.0, 0.01)) for day in range(0, len(loads), 5)}

    result = calibrate_banister(loads, observations, _PRIOR)

    assert result.calibrated is False
    assert result.params == _PRIOR


def test_calibrates_synthetic_banister_performance() -> None:
    loads = _loads()

    result = calibrate_banister(loads, _observations(loads), _PRIOR)

    assert result.calibrated is True
    assert result.r_squared is not None
    assert result.r_squared > 0.3
    assert result.params.p0 == _PRIOR.p0
    assert result.params.k2 > result.params.k1
    assert result.params.tau1 > result.params.tau2
    assert result.params.tau1 == pytest.approx(_TRUE.tau1, rel=0.25)
    assert result.params.tau2 == pytest.approx(_TRUE.tau2, rel=0.25)


def test_calibration_preserves_freshness_scale() -> None:
    loads = _loads()

    result = calibrate_banister(loads, _observations(loads), _PRIOR)

    prior_std = statistics.pstdev(impulse_response(loads, _PRIOR).freshness)
    calibrated_std = statistics.pstdev(impulse_response(loads, result.params).freshness)
    assert calibrated_std == pytest.approx(prior_std, rel=0.05)
