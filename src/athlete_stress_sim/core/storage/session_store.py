"""DuckDB persistence for parsed Polar sessions.

Creates the OLAP model (``athlete``, ``exercises``, ``samples``) and stores
second-by-second telemetry (``RNF-01``, local-only).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from athlete_stress_sim.core.etl.types import Exercise, ParsedSession, SampleRow

_ATHLETE_SCHEMA = """
CREATE TABLE IF NOT EXISTS athlete (
    athlete_id INTEGER PRIMARY KEY,
    polar_user_id VARCHAR,
    created_at TIMESTAMP
)
"""

_EXERCISES_SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
    exercise_id VARCHAR PRIMARY KEY,
    sport VARCHAR,
    sub_sport VARCHAR,
    start_time TIMESTAMP,
    duration_s DOUBLE,
    distance_m DOUBLE,
    calories DOUBLE,
    avg_hr INTEGER,
    max_hr INTEGER,
    total_ascent_m DOUBLE,
    total_descent_m DOUBLE,
    file_path VARCHAR,
    parsed_at TIMESTAMP
)
"""

_SAMPLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    exercise_id VARCHAR NOT NULL,
    ts TIMESTAMP NOT NULL,
    elapsed_s DOUBLE NOT NULL,
    hr INTEGER,
    speed_mps DOUBLE,
    cadence INTEGER,
    altitude_m DOUBLE,
    distance_m DOUBLE,
    is_valid BOOLEAN NOT NULL
)
"""

_RPE_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_rpe (
    exercise_id VARCHAR PRIMARY KEY,
    rpe DOUBLE NOT NULL,
    recorded_at TIMESTAMP
)
"""

_DEFAULT_ATHLETE_ID = 1

_EXERCISE_UPDATE_COLUMNS = frozenset(
    {
        "sport",
        "sub_sport",
        "start_time",
        "duration_s",
        "distance_m",
        "calories",
        "avg_hr",
        "max_hr",
        "total_ascent_m",
        "total_descent_m",
    }
)


class SessionStore:
    """Persist parsed sessions and their telemetry samples.

    Args:
        db_path: Path to the DuckDB file. Parent directories are created if needed.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_revision = 0
        self._ensure_schema()

    def revision(self) -> tuple[str, int, int, int]:
        """Return a key that changes whenever the database file is modified."""
        stat = self._db_path.stat()
        return (
            str(self._db_path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
            self._write_revision,
        )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            for statement in (
                _ATHLETE_SCHEMA,
                _EXERCISES_SCHEMA,
                _SAMPLES_SCHEMA,
                _RPE_SCHEMA,
            ):
                connection.execute(statement)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS samples_exercise_id_idx ON samples (exercise_id)"
            )
        finally:
            connection.close()

    def ensure_athlete(self, polar_user_id: str) -> None:
        """Create the single user-zero athlete row if it does not exist yet."""
        connection = self._connect()
        try:
            connection.execute(
                "INSERT OR IGNORE INTO athlete VALUES (?, ?, ?)",
                [_DEFAULT_ATHLETE_ID, polar_user_id, datetime.now(UTC).replace(tzinfo=None)],
            )
        finally:
            connection.close()
        self._write_revision += 1

    def get_athlete(self) -> str | None:
        """Return the stored Polar user id, or ``None`` if no athlete row exists."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT polar_user_id FROM athlete WHERE athlete_id = ?",
                [_DEFAULT_ATHLETE_ID],
            ).fetchone()
        finally:
            connection.close()
        return str(row[0]) if row is not None else None

    def has_session(self, exercise_id: str) -> bool:
        """Whether an exercise has already been parsed and persisted."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM exercises WHERE exercise_id = ?",
                [exercise_id],
            ).fetchone()
        finally:
            connection.close()
        return row is not None

    def save_session(self, exercise_id: str, session: ParsedSession, file_path: str) -> None:
        """Persist a parsed session, replacing any previous copy of it."""
        metadata = session.metadata
        connection = self._connect()
        try:
            connection.execute("DELETE FROM samples WHERE exercise_id = ?", [exercise_id])
            connection.execute("DELETE FROM exercises WHERE exercise_id = ?", [exercise_id])
            connection.execute(
                "INSERT INTO exercises VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    exercise_id,
                    metadata.sport,
                    metadata.sub_sport,
                    metadata.start_time,
                    metadata.duration_s,
                    metadata.distance_m,
                    metadata.calories,
                    metadata.avg_hr,
                    metadata.max_hr,
                    metadata.total_ascent_m,
                    metadata.total_descent_m,
                    file_path,
                    datetime.now(UTC).replace(tzinfo=None),
                ],
            )
            if session.samples:
                connection.executemany(
                    "INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        [
                            exercise_id,
                            sample.timestamp,
                            sample.elapsed_s,
                            sample.hr,
                            sample.speed_mps,
                            sample.cadence,
                            sample.altitude_m,
                            sample.distance_m,
                            sample.is_valid,
                        ]
                        for sample in session.samples
                    ],
                )
        finally:
            connection.close()
        self._write_revision += 1

    def list_exercises(self) -> list[Exercise]:
        """Return every persisted exercise, most recent first."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT exercise_id, sport, sub_sport, start_time, duration_s, distance_m, "
                "calories, avg_hr, max_hr, total_ascent_m, total_descent_m, file_path "
                "FROM exercises ORDER BY start_time DESC"
            ).fetchall()
        finally:
            connection.close()
        return [_row_to_exercise(row) for row in rows]

    def list_exercises_with_rpe(self) -> list[tuple[Exercise, float | None]]:
        """Return every persisted exercise with its session-RPE in one query.

        Returns:
            ``(exercise, rpe)`` pairs ordered by start time, most recent first.
            ``rpe`` is ``None`` when the session has no recorded RPE.
        """
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT e.exercise_id, e.sport, e.sub_sport, e.start_time, e.duration_s, "
                "e.distance_m, e.calories, e.avg_hr, e.max_hr, e.total_ascent_m, "
                "e.total_descent_m, e.file_path, r.rpe "
                "FROM exercises AS e "
                "LEFT JOIN session_rpe AS r ON r.exercise_id = e.exercise_id "
                "ORDER BY e.start_time DESC"
            ).fetchall()
        finally:
            connection.close()
        return [
            (
                _row_to_exercise(row[:12]),
                float(row[12]) if row[12] is not None else None,
            )
            for row in rows
        ]

    def get_exercise(self, exercise_id: str) -> Exercise | None:
        """Return one persisted exercise, or ``None`` if unknown."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT exercise_id, sport, sub_sport, start_time, duration_s, distance_m, "
                "calories, avg_hr, max_hr, total_ascent_m, total_descent_m, file_path "
                "FROM exercises WHERE exercise_id = ?",
                [exercise_id],
            ).fetchone()
        finally:
            connection.close()
        return _row_to_exercise(row) if row is not None else None

    def set_rpe(self, exercise_id: str, rpe: float) -> None:
        """Store the session-RPE (Borg CR-10) for an exercise."""
        connection = self._connect()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO session_rpe VALUES (?, ?, ?)",
                [exercise_id, rpe, datetime.now(UTC).replace(tzinfo=None)],
            )
        finally:
            connection.close()
        self._write_revision += 1

    def update_exercise(self, exercise_id: str, updates: dict[str, object]) -> None:
        """Update editable metadata fields of one exercise.

        Args:
            exercise_id: Identifier of the persisted exercise.
            updates: Column/value pairs to write; only allow-listed columns are
                accepted so the SQL identifiers cannot be injected.

        Raises:
            ValueError: If ``updates`` contains an unknown column.
        """
        unknown = set(updates) - _EXERCISE_UPDATE_COLUMNS
        if unknown:
            raise ValueError(f"Unsupported exercise fields: {sorted(unknown)}")
        if not updates:
            return
        assignments = ", ".join(f"{column} = ?" for column in updates)
        connection = self._connect()
        try:
            connection.execute(
                f"UPDATE exercises SET {assignments} WHERE exercise_id = ?",
                [*updates.values(), exercise_id],
            )
        finally:
            connection.close()
        self._write_revision += 1

    def get_rpe(self, exercise_id: str) -> float | None:
        """Return the stored session-RPE for an exercise, or ``None``."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT rpe FROM session_rpe WHERE exercise_id = ?",
                [exercise_id],
            ).fetchone()
        finally:
            connection.close()
        return float(row[0]) if row is not None else None

    def count_sessions(self) -> int:
        """Number of exercises persisted."""
        connection = self._connect()
        try:
            row = connection.execute("SELECT COUNT(*) FROM exercises").fetchone()
        finally:
            connection.close()
        return int(row[0]) if row is not None else 0

    def count_samples(self, exercise_id: str) -> int:
        """Number of samples stored for an exercise."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM samples WHERE exercise_id = ?",
                [exercise_id],
            ).fetchone()
        finally:
            connection.close()
        return int(row[0]) if row is not None else 0

    def query_samples(self, exercise_id: str) -> list[SampleRow]:
        """Return the stored samples for an exercise, ordered by elapsed time."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT ts, elapsed_s, hr, speed_mps, cadence, altitude_m, distance_m, is_valid "
                "FROM samples WHERE exercise_id = ? ORDER BY elapsed_s",
                [exercise_id],
            ).fetchall()
        finally:
            connection.close()
        return [_row_to_sample(row) for row in rows]

    def query_all_samples(self) -> dict[str, list[SampleRow]]:
        """Return every stored sample grouped by exercise in one query.

        Returns:
            A mapping from exercise id to its samples ordered by elapsed time.
            Exercises without samples are absent from the mapping.
        """
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT exercise_id, ts, elapsed_s, hr, speed_mps, cadence, altitude_m, "
                "distance_m, is_valid FROM samples ORDER BY exercise_id, elapsed_s"
            ).fetchall()
        finally:
            connection.close()
        grouped: dict[str, list[SampleRow]] = {}
        for row in rows:
            grouped.setdefault(str(row[0]), []).append(_row_to_sample(row[1:]))
        return grouped


def _row_to_sample(row: tuple[Any, ...]) -> SampleRow:
    return SampleRow(
        timestamp=row[0],
        elapsed_s=row[1],
        hr=row[2],
        speed_mps=row[3],
        cadence=row[4],
        altitude_m=row[5],
        distance_m=row[6],
        is_valid=row[7],
    )


def _row_to_exercise(row: tuple[Any, ...]) -> Exercise:
    (
        exercise_id,
        sport,
        sub_sport,
        start_time,
        duration_s,
        distance_m,
        calories,
        avg_hr,
        max_hr,
        total_ascent_m,
        total_descent_m,
        file_path,
    ) = row
    return Exercise(
        exercise_id=str(exercise_id),
        sport=str(sport),
        sub_sport=str(sub_sport),
        start_time=start_time,
        duration_s=duration_s,
        distance_m=distance_m,
        calories=calories,
        avg_hr=avg_hr,
        max_hr=max_hr,
        total_ascent_m=total_ascent_m,
        total_descent_m=total_descent_m,
        file_path=str(file_path),
    )
