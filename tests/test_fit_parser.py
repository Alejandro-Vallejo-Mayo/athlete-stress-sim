"""Integration tests for the FIT parser using synthetic FIT files."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from athlete_stress_sim.core.etl.fit_parser import FITParser
from tests.helpers.fit_fixture import RecordSpec, write_activity_fit

_START = datetime(2026, 10, 3, 7, 21, 27)


def _records() -> list[RecordSpec]:
    return [
        RecordSpec(
            timestamp=_START + timedelta(seconds=i),
            hr=120 + i,
            speed_mps=2.5,
            cadence=80 + i,
            altitude_m=10.0 + i,
            distance_m=2.5 * i,
        )
        for i in range(5)
    ]


def test_parse_extracts_session_metadata(tmp_path: Path) -> None:
    path = write_activity_fit(tmp_path / "run.fit", _records(), sport=1)

    session = FITParser().parse(path)

    assert session.metadata.sport == "running"
    assert session.metadata.start_time == _START
    assert session.metadata.duration_s == 4.0
    assert session.metadata.distance_m == 10.0
    assert session.metadata.calories == 500.0
    assert session.metadata.avg_hr == 122
    assert session.metadata.max_hr == 124


def test_parse_extracts_second_by_second_samples(tmp_path: Path) -> None:
    path = write_activity_fit(tmp_path / "run.fit", _records())

    session = FITParser().parse(path)

    assert len(session.samples) == 5
    first = session.samples[0]
    assert first.timestamp == _START
    assert first.elapsed_s == 0.0
    assert first.hr == 120
    assert first.speed_mps == 2.5
    assert first.cadence == 80
    assert first.altitude_m == 10.0
    assert first.distance_m == 0.0
    assert all(sample.is_valid for sample in session.samples)


def test_parse_single_record(tmp_path: Path) -> None:
    path = write_activity_fit(tmp_path / "single.fit", _records()[:1])

    session = FITParser().parse(path)

    assert len(session.samples) == 1
    assert session.samples[0].hr == 120
