"""Unit tests for race time prediction (``RF-05.4``)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from athlete_stress_sim.core.etl.types import Sample
from athlete_stress_sim.core.metrics.race_prediction import (
    Confidence,
    Effort,
    EffortSource,
    EffortTier,
    PredictionModel,
    best_effort,
    classify_effort,
    fit_critical_speed,
    format_duration,
    predict_race,
    riegel_time,
)

_DAY = date(2026, 10, 1)
_START = datetime(2026, 10, 1, 7, 0, 0)
_HR_REST = 55.0
_HR_MAX = 199.0
_HALF_MARATHON_KM = 21.0975


def _samples(distance_m: float, duration_s: float, hr: int) -> list[Sample]:
    steps = int(duration_s)
    speed = distance_m / duration_s
    return [
        Sample(
            timestamp=_START + timedelta(seconds=index),
            elapsed_s=float(index),
            hr=hr,
            speed_mps=speed,
            distance_m=distance_m * index / duration_s,
            is_valid=True,
        )
        for index in range(steps + 1)
    ]


def _effort(
    distance_km: float,
    time_s: float,
    tier: EffortTier,
    *,
    relative_hr: float | None = None,
    efficiency: float | None = None,
    source: EffortSource = EffortSource.TRAINING,
    fitness_factor: float = 1.0,
) -> Effort:
    return Effort(
        distance_km=distance_km,
        time_s=time_s,
        day=_DAY,
        avg_hr=None,
        relative_hr=relative_hr,
        efficiency=efficiency,
        tier=tier,
        source=source,
        fitness_factor=fitness_factor,
    )


def _critical_efforts() -> list[Effort]:
    cs = 3.0
    d_prime = 200.0
    return [
        _effort(3.0, (3000.0 - d_prime) / cs, EffortTier.RACE),
        _effort(5.0, (5000.0 - d_prime) / cs, EffortTier.RACE),
        _effort(10.0, (10000.0 - d_prime) / cs, EffortTier.RACE),
    ]


def test_best_effort_returns_fastest_segment() -> None:
    effort = best_effort(
        _samples(5000.0, 1600.0, 180),
        5000.0,
        _DAY,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert effort is not None
    assert effort.distance_km == pytest.approx(5.0)
    assert effort.time_s == pytest.approx(1600.0)
    assert effort.avg_hr == pytest.approx(180.0)
    assert effort.relative_hr == pytest.approx((180.0 - _HR_REST) / (_HR_MAX - _HR_REST))
    assert effort.tier is EffortTier.HARD
    assert effort.efficiency == pytest.approx((5000.0 / 1600.0) / 180.0)


def test_best_effort_returns_none_when_activity_is_short() -> None:
    effort = best_effort(
        _samples(1000.0, 300.0, 150),
        5000.0,
        _DAY,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert effort is None


def test_best_effort_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        best_effort(_samples(1000.0, 300.0, 150), 0.0, _DAY, hr_rest=55, hr_max=199)
    with pytest.raises(ValueError):
        best_effort(_samples(1000.0, 300.0, 150), 1000.0, _DAY, hr_rest=199, hr_max=199)


@pytest.mark.parametrize(
    ("relative_hr", "expected"),
    [
        (0.90, EffortTier.RACE),
        (0.85, EffortTier.HARD),
        (0.75, EffortTier.MODERATE),
        (0.50, EffortTier.EASY),
        (None, EffortTier.UNKNOWN),
    ],
)
def test_classify_effort_tiers(
    relative_hr: float | None,
    expected: EffortTier,
) -> None:
    assert classify_effort(relative_hr) is expected


def test_riegel_time_scales_with_distance() -> None:
    expected = 3600.0 * (_HALF_MARATHON_KM / 10.0) ** 1.06

    assert riegel_time(10.0, 3600.0, _HALF_MARATHON_KM, 1.06) == pytest.approx(expected)


def test_riegel_time_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        riegel_time(0.0, 3600.0, 10.0)
    with pytest.raises(ValueError):
        riegel_time(10.0, 0.0, 21.0)
    with pytest.raises(ValueError):
        riegel_time(10.0, 3600.0, 21.0, exponent=2.0)


def test_fit_critical_speed_recovers_known_parameters() -> None:
    fit = fit_critical_speed(_critical_efforts(), hr_rest=_HR_REST, hr_max=_HR_MAX)

    assert fit is not None
    assert fit.cs_mps == pytest.approx(3.0)
    assert fit.d_prime_m == pytest.approx(200.0)
    assert fit.r_squared == pytest.approx(1.0)


def test_fit_critical_speed_requires_quality_efforts() -> None:
    easy = [
        _effort(3.0, 1200.0, EffortTier.EASY),
        _effort(5.0, 2100.0, EffortTier.EASY),
        _effort(10.0, 4500.0, EffortTier.EASY),
    ]

    assert fit_critical_speed(easy, hr_rest=_HR_REST, hr_max=_HR_MAX) is None


def test_hard_effort_is_hr_adjusted_to_race_effort() -> None:
    effort = Effort(
        distance_km=5.0,
        time_s=1800.0,
        day=_DAY,
        avg_hr=170.0,
        relative_hr=0.80,
        efficiency=(5000.0 / 1800.0) / 170.0,
        tier=EffortTier.HARD,
    )
    race_hr = _HR_REST + effort.race_hr_ratio() * (_HR_MAX - _HR_REST)
    correction = race_hr / 170.0

    assert effort.race_hr_ratio() == pytest.approx(0.93)
    assert effort.hr_correction(_HR_REST, _HR_MAX) == pytest.approx(correction)
    assert effort.race_equivalent_time_s(_HR_REST, _HR_MAX) == pytest.approx(1800.0 / correction)


def test_race_effort_is_not_hr_adjusted() -> None:
    effort = Effort(
        distance_km=5.0,
        time_s=1800.0,
        day=_DAY,
        avg_hr=190.0,
        relative_hr=0.95,
        efficiency=(5000.0 / 1800.0) / 190.0,
        tier=EffortTier.RACE,
    )

    assert effort.hr_correction(_HR_REST, _HR_MAX) == pytest.approx(1.0)
    assert effort.race_equivalent_time_s(_HR_REST, _HR_MAX) == pytest.approx(effort.adjusted_time_s)


def test_hard_reference_predicts_faster_than_its_own_time() -> None:
    effort = Effort(
        distance_km=5.0,
        time_s=1800.0,
        day=_DAY,
        avg_hr=170.0,
        relative_hr=0.80,
        efficiency=(5000.0 / 1800.0) / 170.0,
        tier=EffortTier.HARD,
    )

    prediction = predict_race(
        5.0,
        [effort],
        model=PredictionModel.RIEGEL,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.predicted_time_s is not None
    assert prediction.predicted_time_s < 1800.0
    assert any("HR-adjusted" in note for note in prediction.notes)


def test_auto_uses_critical_speed_when_enough_quality_efforts() -> None:
    prediction = predict_race(
        _HALF_MARATHON_KM,
        _critical_efforts(),
        model=PredictionModel.AUTO,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.model is PredictionModel.CRITICAL_SPEED
    assert prediction.confidence is Confidence.HIGH
    assert prediction.predicted_time_s == pytest.approx((21097.5 - 200.0) / 3.0)
    assert prediction.fast_time_s is not None
    assert prediction.slow_time_s is not None
    assert prediction.fast_time_s <= prediction.predicted_time_s <= prediction.slow_time_s


def test_auto_uses_riegel_with_one_hard_effort() -> None:
    effort = _effort(10.0, 3600.0, EffortTier.HARD)

    prediction = predict_race(
        _HALF_MARATHON_KM,
        [effort],
        model=PredictionModel.AUTO,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.model is PredictionModel.RIEGEL
    assert prediction.confidence is Confidence.MEDIUM
    assert prediction.predicted_time_s == pytest.approx(
        riegel_time(10.0, 3600.0, _HALF_MARATHON_KM, 1.06)
    )


def test_auto_extrapolates_from_easy_efforts_instead_of_slow_pace() -> None:
    easy = _effort(
        5.0,
        1800.0,
        EffortTier.EASY,
        relative_hr=0.59,
        efficiency=(5000.0 / 1800.0) / 140.0,
    )

    prediction = predict_race(
        10.0,
        [easy],
        model=PredictionModel.AUTO,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.model is PredictionModel.HR_EXTRAPOLATION
    assert prediction.confidence is Confidence.LOW
    assert prediction.predicted_time_s is not None
    assert prediction.predicted_time_s < riegel_time(5.0, 1800.0, 10.0, 1.06)


def test_predict_without_efforts_returns_none() -> None:
    prediction = predict_race(
        10.0,
        [],
        model=PredictionModel.AUTO,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.model is PredictionModel.NONE
    assert prediction.confidence is Confidence.NONE
    assert prediction.predicted_time_s is None


def test_fitness_adjustment_makes_improved_athlete_faster() -> None:
    base = _effort(10.0, 3600.0, EffortTier.RACE)
    improved = replace(base, fitness_factor=1.2)

    base_prediction = predict_race(
        _HALF_MARATHON_KM,
        [base],
        model=PredictionModel.RIEGEL,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )
    improved_prediction = predict_race(
        _HALF_MARATHON_KM,
        [improved],
        model=PredictionModel.RIEGEL,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert base_prediction.predicted_time_s is not None
    assert improved_prediction.predicted_time_s is not None
    assert improved_prediction.predicted_time_s < base_prediction.predicted_time_s
    assert any("fitness" in note for note in improved_prediction.notes)


def test_manual_reference_is_used() -> None:
    manual = _effort(10.0, 3300.0, EffortTier.RACE, source=EffortSource.MANUAL)
    training = _effort(5.0, 1600.0, EffortTier.HARD)

    prediction = predict_race(
        _HALF_MARATHON_KM,
        [training],
        model=PredictionModel.RIEGEL,
        reference=manual,
        hr_rest=_HR_REST,
        hr_max=_HR_MAX,
    )

    assert prediction.predicted_time_s == pytest.approx(
        riegel_time(10.0, 3300.0, _HALF_MARATHON_KM, 1.06)
    )
    assert any("manual" in note for note in prediction.notes)


def test_predict_race_rejects_invalid_target() -> None:
    with pytest.raises(ValueError):
        predict_race(
            0.0,
            _critical_efforts(),
            hr_rest=_HR_REST,
            hr_max=_HR_MAX,
        )


def test_format_duration() -> None:
    assert format_duration(3661.0) == "1:01:01"
    assert format_duration(125.0) == "2:05"
