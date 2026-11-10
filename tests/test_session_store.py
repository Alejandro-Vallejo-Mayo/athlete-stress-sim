"""Unit tests for the DuckDB session store."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from athlete_stress_sim.core.etl.types import ParsedSession, Sample, SessionMetadata
from athlete_stress_sim.core.storage.session_store import SessionStore

_START = datetime(2026, 10, 3, 7, 0, 0)


def _session() -> ParsedSession:
    return ParsedSession(
        metadata=SessionMetadata(
            sport="running",
            sub_sport="generic",
            start_time=_START,
            duration_s=2.0,
            distance_m=5.0,
            calories=100.0,
            avg_hr=121,
            max_hr=122,
        ),
        samples=[
            Sample(timestamp=_START, elapsed_s=0.0, hr=120, speed_mps=2.5, cadence=80),
            Sample(timestamp=_START, elapsed_s=1.0, hr=122, speed_mps=2.6, cadence=81),
        ],
    )


def test_has_session_is_false_when_empty(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")

    assert not store.has_session("abc")
    assert store.count_sessions() == 0


def test_save_session_persists_metadata_and_samples(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")

    store.save_session("abc", _session(), "data/raw/abc.fit")

    assert store.has_session("abc")
    assert store.count_sessions() == 1
    assert store.count_samples("abc") == 2
    samples = store.query_samples("abc")
    assert [sample.hr for sample in samples] == [120, 122]
    assert samples[0].timestamp == _START


def test_save_session_is_idempotent(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("abc", _session(), "data/raw/abc.fit")

    store.save_session("abc", _session(), "data/raw/abc.fit")

    assert store.count_sessions() == 1
    assert store.count_samples("abc") == 2


def test_ensure_athlete_creates_a_single_row(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")

    store.ensure_athlete("56232817")
    store.ensure_athlete("99999999")

    assert store.get_athlete() == "56232817"


def test_list_and_get_exercise(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("abc", _session(), "data/raw/abc.fit")

    exercises = store.list_exercises()

    assert [exercise.exercise_id for exercise in exercises] == ["abc"]
    exercise = store.get_exercise("abc")
    assert exercise is not None
    assert exercise.sport == "running"
    assert exercise.duration_s == 2.0
    assert exercise.file_path == "data/raw/abc.fit"
    assert store.get_exercise("missing") is None


def test_rpe_roundtrip_and_overwrite(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("abc", _session(), "data/raw/abc.fit")

    assert store.get_rpe("abc") is None

    store.set_rpe("abc", 7.0)
    assert store.get_rpe("abc") == 7.0

    store.set_rpe("abc", 5.0)
    assert store.get_rpe("abc") == 5.0


def test_list_exercises_with_rpe_joins_the_recorded_value(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("abc", _session(), "data/raw/abc.fit")

    assert store.list_exercises_with_rpe()[0][1] is None

    store.set_rpe("abc", 7.0)

    exercises = store.list_exercises_with_rpe()
    assert [exercise.exercise_id for exercise, _ in exercises] == ["abc"]
    assert exercises[0][1] == 7.0


def test_query_all_samples_groups_samples_by_exercise(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")
    store.save_session("abc", _session(), "data/raw/abc.fit")
    store.save_session("def", _session(), "data/raw/def.fit")

    grouped = store.query_all_samples()

    assert set(grouped) == {"abc", "def"}
    assert [sample.hr for sample in grouped["abc"]] == [120, 122]
    assert [sample.hr for sample in grouped["def"]] == [120, 122]


def test_query_all_samples_is_empty_without_samples(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.duckdb")

    assert store.query_all_samples() == {}
