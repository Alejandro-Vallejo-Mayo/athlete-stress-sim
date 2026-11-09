"""Unit tests for observed running performance (``RF-03.2``)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from athlete_stress_sim.core.etl.types import Sample
from athlete_stress_sim.core.metrics.performance import (
    performance_observations,
    session_efficiency,
)

_START = datetime(2026, 10, 3, 7, 0, 0)


def _sample(elapsed_s: float, speed: float | None, hr: int | None) -> Sample:
    return Sample(
        timestamp=_START + timedelta(seconds=elapsed_s),
        elapsed_s=elapsed_s,
        hr=hr,
        speed_mps=speed,
        distance_m=elapsed_s * 3.0,
        is_valid=True,
    )


def test_session_efficiency_averages_valid_samples() -> None:
    samples = [_sample(0.0, 3.0, 150), _sample(1.0, 2.7, 150)]

    assert session_efficiency(samples) == pytest.approx(0.019)


def test_session_efficiency_skips_invalid_samples() -> None:
    samples = [
        _sample(0.0, 3.0, 150),
        _sample(1.0, None, 150),
        _sample(2.0, 3.0, None),
        _sample(3.0, 0.0, 150),
    ]

    assert session_efficiency(samples) == pytest.approx(0.02)


@pytest.mark.parametrize(
    "samples",
    [[], [_sample(0.0, None, 150), _sample(1.0, 3.0, 0)]],
)
def test_session_efficiency_without_valid_samples_is_none(samples: list[Sample]) -> None:
    assert session_efficiency(samples) is None


def test_performance_observations_map_dates_to_indices() -> None:
    dates = [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]

    observations = performance_observations(
        dates,
        [(date(2026, 10, 1), 0.02), (date(2026, 10, 3), 0.018)],
    )

    assert observations == pytest.approx({0: 0.02, 2: 0.018})
    assert list(observations) == [0, 2]


def test_performance_observations_average_same_day() -> None:
    dates = [date(2026, 10, 1), date(2026, 10, 2)]

    observations = performance_observations(
        dates,
        [(date(2026, 10, 1), 0.02), (date(2026, 10, 1), 0.018)],
    )

    assert observations == pytest.approx({0: 0.019})


def test_performance_observations_ignore_missing_and_unknown_dates() -> None:
    dates = [date(2026, 10, 1), date(2026, 10, 2)]

    observations = performance_observations(
        dates,
        [
            (date(2026, 10, 1), None),
            (date(2026, 10, 2), 0.02),
            (date(2026, 9, 30), 0.03),
        ],
    )

    assert observations == pytest.approx({1: 0.02})


def test_performance_observations_empty() -> None:
    assert performance_observations([], []) == {}
