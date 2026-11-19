"""Unit tests for FIT record normalization and gap detection."""

from __future__ import annotations

from datetime import datetime, timedelta

from athlete_stress_sim.core.etl.normalize import find_gaps, normalize_records
from athlete_stress_sim.core.etl.types import RawRecord

_START = datetime(2026, 10, 3, 7, 0, 0)


def _record(offset_s: int, **values: float) -> RawRecord:
    return RawRecord(timestamp=_START + timedelta(seconds=offset_s), **values)


def test_normalize_computes_elapsed_and_keeps_valid_values() -> None:
    records = [
        _record(0, hr=120, speed_mps=2.5, cadence=80, altitude_m=10.0, distance_m=0.0),
        _record(1, hr=121, speed_mps=2.6, cadence=81, altitude_m=10.5, distance_m=2.6),
    ]

    samples = normalize_records(records)

    assert [sample.elapsed_s for sample in samples] == [0.0, 1.0]
    assert samples[1].hr == 121
    assert samples[1].speed_mps == 2.6
    assert all(sample.is_valid for sample in samples)


def test_normalize_flags_outliers_but_keeps_the_sample() -> None:
    records = [
        _record(0, hr=300, speed_mps=-1.0, cadence=400, altitude_m=10.0),
        _record(1, hr=120, speed_mps=2.5, cadence=80, altitude_m=10.0),
    ]

    samples = normalize_records(records)

    assert len(samples) == 2
    assert samples[0].hr is None
    assert samples[0].speed_mps is None
    assert samples[0].cadence is None
    assert samples[0].is_valid is False
    assert samples[1].is_valid is True


def test_normalize_ignores_records_without_timestamp() -> None:
    records = [RawRecord(hr=120), _record(0, hr=130)]

    samples = normalize_records(records)

    assert len(samples) == 1
    assert samples[0].hr == 130


def test_normalize_sorts_by_timestamp() -> None:
    records = [_record(2, hr=122), _record(0, hr=120), _record(1, hr=121)]

    samples = normalize_records(records)

    assert [sample.hr for sample in samples] == [120, 121, 122]
    assert samples[0].elapsed_s == 0.0


def test_find_gaps_detects_jumps() -> None:
    records = [
        _record(0, hr=120),
        _record(1, hr=120),
        _record(2, hr=120),
        _record(60, hr=120),
        _record(61, hr=120),
    ]

    samples = normalize_records(records)
    gaps = find_gaps(samples)

    assert len(gaps) == 1
    assert gaps[0] == (_START + timedelta(seconds=2), _START + timedelta(seconds=60))


def test_find_gaps_returns_empty_for_short_series() -> None:
    samples = normalize_records([_record(0, hr=120), _record(1, hr=120)])

    assert find_gaps(samples) == []
