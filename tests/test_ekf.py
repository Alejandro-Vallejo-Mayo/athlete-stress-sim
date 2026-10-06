"""Tests for the Banister parameter-estimation EKF (synthetic convergence)."""

from __future__ import annotations

import numpy as np
import pytest

from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response
from athlete_stress_sim.core.models.ekf import BanisterEKF

TRUE_PARAMS = BanisterParams(p0=0.0, k1=1.0, k2=2.0, tau1=45.0, tau2=15.0)
_PRIOR = BanisterParams(k1=1.0, k2=2.0, tau1=42.0, tau2=12.0)


def _synthetic() -> tuple[list[float], dict[int, float], float]:
    """Build a 300-day load block with noisy weekly performance observations."""
    n_days = 300
    loads: list[float] = []
    for week in range(n_days // 7 + 1):
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
    loads = loads[:n_days]
    truth = impulse_response(loads, TRUE_PARAMS)
    rng = np.random.default_rng(1)
    sigma = 0.02 * float(np.mean([abs(value) for value in truth.performance]))
    observations = {
        day: truth.performance[day] + float(rng.normal(0.0, sigma)) for day in range(4, n_days, 5)
    }
    return loads, observations, sigma


def test_estimates_gains_close_to_truth() -> None:
    loads, observations, sigma = _synthetic()

    ekf = BanisterEKF(_PRIOR, measurement_noise=sigma**2)
    ekf.run(loads, observations)

    assert ekf.parameters.k1 == pytest.approx(TRUE_PARAMS.k1, rel=0.10)
    assert ekf.parameters.k2 == pytest.approx(TRUE_PARAMS.k2, rel=0.10)


def test_time_constants_stay_physiological() -> None:
    loads, observations, sigma = _synthetic()

    ekf = BanisterEKF(_PRIOR, measurement_noise=sigma**2)
    ekf.run(loads, observations)

    params = ekf.parameters
    assert params.tau1 > params.tau2
    assert 20.0 <= params.tau1 <= 90.0
    assert 5.0 <= params.tau2 <= 30.0


def test_estimated_model_tracks_observations() -> None:
    loads, observations, sigma = _synthetic()

    ekf = BanisterEKF(_PRIOR, measurement_noise=sigma**2)
    ekf.run(loads, observations)
    estimated = impulse_response(loads, ekf.parameters)

    days = sorted(observations)
    measured = np.array([observations[day] for day in days])
    predicted = np.array([estimated.performance[day] for day in days])
    ss_res = float(np.sum((measured - predicted) ** 2))
    ss_tot = float(np.sum((measured - measured.mean()) ** 2))

    assert 1.0 - ss_res / ss_tot > 0.9


def test_initial_state_uses_priors() -> None:
    ekf = BanisterEKF(_PRIOR)

    fitness, fatigue, k1, k2, tau1, tau2 = ekf.state

    assert (fitness, fatigue) == (0.0, 0.0)
    assert (k1, k2, tau1, tau2) == (1.0, 2.0, 42.0, 12.0)
