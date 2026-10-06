"""Unit tests for the Banister fitness-fatigue model."""

from __future__ import annotations

import math
import time

import pytest
from pydantic import ValidationError

from athlete_stress_sim.core.models.banister import (
    BanisterParams,
    impulse_response,
    solve_banister_ode,
)

PARAMS = BanisterParams(p0=0.0, k1=1.0, k2=2.0, tau1=45.0, tau2=15.0)


def test_empty_series_returns_empty() -> None:
    result = impulse_response([], PARAMS)

    assert result.fitness == []
    assert result.performance == []


def test_single_impulse_dips_then_recovers() -> None:
    result = impulse_response([100.0] + [0.0] * 120, PARAMS)

    assert result.freshness[0] < 0.0
    assert result.freshness[-1] > 0.0


def test_fatigue_decays_faster_than_fitness() -> None:
    result = impulse_response([100.0] + [0.0] * 60, PARAMS)

    fitness_ratio = result.fitness[30] / result.fitness[29]
    fatigue_ratio = result.fatigue[30] / result.fatigue[29]
    assert fitness_ratio > fatigue_ratio
    assert fitness_ratio == pytest.approx(math.exp(-1.0 / PARAMS.tau1))
    assert fatigue_ratio == pytest.approx(math.exp(-1.0 / PARAMS.tau2))


def test_performance_is_p0_plus_freshness() -> None:
    params = BanisterParams(p0=5.0)
    result = impulse_response([100.0, 50.0, 0.0], params)

    for net, performance in zip(result.freshness, result.performance, strict=True):
        assert performance == pytest.approx(params.p0 + net)


def test_tapering_raises_freshness() -> None:
    result = impulse_response([100.0] * 60 + [0.0] * 40, PARAMS)

    assert max(result.freshness[60:]) > result.freshness[59]


def test_numeric_decay_rate_matches_analytic() -> None:
    loads = [100.0] + [0.0] * 100
    numeric = solve_banister_ode(loads, PARAMS)
    analytic = impulse_response(loads, PARAMS)

    for series in (numeric, analytic):
        ratio = series.fitness[40] / series.fitness[39]
        assert ratio == pytest.approx(math.exp(-1.0 / PARAMS.tau1), rel=1e-4)


def test_numeric_steady_state_close_to_analytic() -> None:
    loads = [100.0] * 400
    numeric = solve_banister_ode(loads, PARAMS)
    analytic = impulse_response(loads, PARAMS)

    assert numeric.fitness[-1] == pytest.approx(analytic.fitness[-1], rel=0.05)
    assert numeric.fatigue[-1] == pytest.approx(analytic.fatigue[-1], rel=0.05)


def test_params_reject_non_positive_tau() -> None:
    with pytest.raises(ValidationError):
        BanisterParams(tau1=0.0)


def test_bench_analytic_under_half_second() -> None:
    loads = [100.0] * 3650

    start = time.perf_counter()
    impulse_response(loads, PARAMS)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5


def test_bench_numeric_under_half_second() -> None:
    loads = [100.0] * 365

    start = time.perf_counter()
    solve_banister_ode(loads, PARAMS)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5
