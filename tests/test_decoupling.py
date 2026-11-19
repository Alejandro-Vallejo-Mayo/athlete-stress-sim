"""Unit tests for the aerobic decoupling metric (``RF-05.3``)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from athlete_stress_sim.core.etl.types import Sample
from athlete_stress_sim.core.metrics.decoupling import (
    aerobic_decoupling,
    efficiency_factor,
    per_km_efficiency,
)

_START = datetime(2026, 10, 3, 7, 0, 0)
_SAMPLES_PER_KM = 10


def _run(speeds: list[float], hr: int = 150) -> list[Sample]:
    samples: list[Sample] = []
    elapsed = 0.0
    for km, speed in enumerate(speeds):
        for i in range(_SAMPLES_PER_KM):
            samples.append(
                Sample(
                    timestamp=_START + timedelta(seconds=elapsed),
                    elapsed_s=elapsed,
                    hr=hr,
                    speed_mps=speed,
                    distance_m=km * 1000.0 + i * 100.0,
                    is_valid=True,
                )
            )
            elapsed += 1.0
    return samples


def test_efficiency_factor_is_speed_over_hr() -> None:
    assert efficiency_factor(3.0, 150) == pytest.approx(0.02)


@pytest.mark.parametrize(
    ("speed", "hr"),
    [(None, 150), (3.0, None), (0.0, 150), (-1.0, 150), (3.0, 0)],
)
def test_efficiency_factor_invalid_inputs(speed: float | None, hr: int | None) -> None:
    assert efficiency_factor(speed, hr) is None


def test_per_km_efficiency_averages_within_each_kilometre() -> None:
    efficiency = per_km_efficiency(_run([3.0, 2.7]))

    assert efficiency == pytest.approx([0.02, 0.018])


def test_per_km_efficiency_skips_invalid_samples() -> None:
    samples = _run([3.0])
    samples[0] = samples[0].model_copy(update={"speed_mps": None})
    samples[1] = samples[1].model_copy(update={"hr": None})

    efficiency = per_km_efficiency(samples)

    assert efficiency == pytest.approx([0.02])


def test_per_km_efficiency_without_data_is_empty() -> None:
    assert per_km_efficiency([]) == []


def test_aerobic_decoupling_positive_when_ef_drops() -> None:
    assert aerobic_decoupling(_run([3.0, 2.7])) == pytest.approx(10.0)


def test_aerobic_decoupling_negative_when_ef_rises() -> None:
    assert aerobic_decoupling(_run([2.7, 3.0])) == pytest.approx(-11.111, rel=1e-3)


def test_aerobic_decoupling_needs_two_kilometres() -> None:
    assert aerobic_decoupling(_run([3.0])) is None
