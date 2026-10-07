"""Unit tests for the ACWR / EWMA metric."""

from __future__ import annotations

import pytest

from athlete_stress_sim.core.metrics.acwr import (
    RiskZone,
    acwr_series,
    classify_risk,
    ewma_lambda,
    ewma_series,
)


def test_ewma_lambda_values() -> None:
    assert ewma_lambda(7) == pytest.approx(0.25)
    assert ewma_lambda(28) == pytest.approx(2 / 29)


def test_ewma_lambda_requires_positive_days() -> None:
    with pytest.raises(ValueError, match="days"):
        ewma_lambda(0)


def test_ewma_series_seed_is_first_value() -> None:
    assert ewma_series([5.0], 0.25) == [5.0]


def test_ewma_series_constant_stays_constant() -> None:
    assert ewma_series([100.0, 100.0, 100.0], 0.25) == pytest.approx([100.0, 100.0, 100.0])


def test_ewma_series_matches_recursion() -> None:
    assert ewma_series([0.0, 100.0], 0.25) == pytest.approx([0.0, 25.0])


def test_ewma_series_empty() -> None:
    assert ewma_series([], 0.25) == []


def test_ewma_series_rejects_bad_lambda() -> None:
    with pytest.raises(ValueError, match="lam"):
        ewma_series([1.0], 0.0)


def test_acwr_of_constant_load_is_one() -> None:
    series = acwr_series([100.0] * 30)

    assert all(value == pytest.approx(1.0) for value in series)


def test_acwr_rises_after_a_spike() -> None:
    series = acwr_series([100.0] * 28 + [400.0])

    assert series[-1] > 1.0


def test_acwr_is_zero_before_any_load() -> None:
    assert acwr_series([0.0, 0.0]) == pytest.approx([0.0, 0.0])


@pytest.mark.parametrize(
    ("value", "zone"),
    [
        (0.5, RiskZone.UNDERTRAINING),
        (0.79, RiskZone.UNDERTRAINING),
        (0.8, RiskZone.SWEET_SPOT),
        (1.3, RiskZone.SWEET_SPOT),
        (1.31, RiskZone.WARNING),
        (1.5, RiskZone.WARNING),
        (1.51, RiskZone.DANGER),
    ],
)
def test_classify_risk_thresholds(value: float, zone: RiskZone) -> None:
    assert classify_risk(value) is zone
