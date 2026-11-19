"""DuckDB-backed registry of ingested Polar exercises.

Tracks which exercises have already been downloaded so the catch-up sync is
idempotent, and doubles as the pending queue for the parser built in S4.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import duckdb
from pydantic import BaseModel

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_log (
    exercise_id VARCHAR PRIMARY KEY,
    file_path VARCHAR NOT NULL,
    file_format VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    error VARCHAR NOT NULL,
    updated_at_epoch BIGINT NOT NULL
)
"""


class IngestStatus(StrEnum):
    """Lifecycle of a downloaded exercise in the ingest log."""

    DOWNLOADED = "downloaded"
    FAILED = "failed"


class IngestRecord(BaseModel):
    """One row of the ingest log."""

    exercise_id: str
    file_path: str = ""
    file_format: str = ""
    status: IngestStatus
    error: str = ""
    updated_at: datetime


class IngestStore:
    """Persist the ingest state of each Polar exercise.

    Args:
        db_path: Path to the DuckDB file. Parent directories are created if needed.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(_SCHEMA)
        finally:
            connection.close()

    def is_downloaded(self, exercise_id: str) -> bool:
        """Whether a successful download is already recorded for ``exercise_id``."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM ingest_log WHERE exercise_id = ? AND status = ?",
                [exercise_id, IngestStatus.DOWNLOADED.value],
            ).fetchone()
        finally:
            connection.close()
        return row is not None

    def mark_downloaded(self, exercise_id: str, file_path: str, file_format: str) -> None:
        """Record a successful download."""
        self._upsert(exercise_id, file_path, file_format, IngestStatus.DOWNLOADED, "")

    def mark_failed(self, exercise_id: str, error: str) -> None:
        """Record a failed download attempt."""
        self._upsert(exercise_id, "", "", IngestStatus.FAILED, error)

    def get(self, exercise_id: str) -> IngestRecord | None:
        """Return the record for ``exercise_id``, or ``None``."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT exercise_id, file_path, file_format, status, error, updated_at_epoch "
                "FROM ingest_log WHERE exercise_id = ?",
                [exercise_id],
            ).fetchone()
        finally:
            connection.close()
        return _row_to_record(row) if row is not None else None

    def list_all(self) -> list[IngestRecord]:
        """Return every recorded exercise, newest first."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT exercise_id, file_path, file_format, status, error, updated_at_epoch "
                "FROM ingest_log ORDER BY updated_at_epoch DESC"
            ).fetchall()
        finally:
            connection.close()
        return [_row_to_record(row) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        """Return the number of records per status."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT status, COUNT(*) FROM ingest_log GROUP BY status"
            ).fetchall()
        finally:
            connection.close()
        return {str(status): int(count) for status, count in rows}

    def _upsert(
        self,
        exercise_id: str,
        file_path: str,
        file_format: str,
        status: IngestStatus,
        error: str,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?, ?)",
                [
                    exercise_id,
                    file_path,
                    file_format,
                    status.value,
                    error,
                    int(datetime.now(UTC).timestamp()),
                ],
            )
        finally:
            connection.close()


def _row_to_record(row: tuple[object, ...]) -> IngestRecord:
    exercise_id, file_path, file_format, status, error, updated_at_epoch = row
    return IngestRecord(
        exercise_id=str(exercise_id),
        file_path=str(file_path),
        file_format=str(file_format),
        status=IngestStatus(str(status)),
        error=str(error),
        updated_at=datetime.fromtimestamp(int(str(updated_at_epoch)), UTC),
    )
