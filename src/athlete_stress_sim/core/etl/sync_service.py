"""Catch-up synchronization of Polar exercises into local raw storage.

Lists the exercises available in Polar, downloads the ones that have not been
ingested yet (idempotent) and records the outcome in the ingest log. This runs
on demand (dashboard button / ``POST /sync``) and once at backend startup, so
the local database catches up whenever the app is opened.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from athlete_stress_sim.core.etl.polar_client import PolarAPIError, PolarClient
from athlete_stress_sim.core.storage.ingest_store import IngestStore

logger = logging.getLogger(__name__)

DEFAULT_FILE_FORMAT = "fit"


class SyncResult(BaseModel):
    """Summary of one synchronization run."""

    listed: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class SyncService:
    """Download newly available Polar exercises, skipping known ones.

    Args:
        client: Polar API client used to list and download exercises.
        store: Ingest log used to make the sync idempotent.
        raw_data_dir: Directory where raw files are written.
        file_format: Raw format to download (``fit`` by default).
    """

    def __init__(
        self,
        client: PolarClient,
        store: IngestStore,
        raw_data_dir: Path | str,
        file_format: str = DEFAULT_FILE_FORMAT,
    ) -> None:
        self._client = client
        self._store = store
        self._raw_data_dir = Path(raw_data_dir)
        self._file_format = file_format

    def sync(self) -> SyncResult:
        """Run one catch-up pass and return a summary.

        Raises:
            PolarAuthError: If no Polar account is linked yet.
        """
        exercises = self._client.list_exercises()
        result = SyncResult(listed=len(exercises))
        self._raw_data_dir.mkdir(parents=True, exist_ok=True)

        for exercise in exercises:
            if self._store.is_downloaded(exercise.exercise_id):
                result.skipped += 1
                continue
            try:
                content = self._client.download_exercise_file(
                    exercise.exercise_id, self._file_format
                )
                path = self._write_file(exercise.exercise_id, content)
                self._store.mark_downloaded(exercise.exercise_id, str(path), self._file_format)
                result.downloaded += 1
                logger.info("Downloaded Polar exercise %s", exercise.exercise_id)
            except (PolarAPIError, OSError) as exc:
                result.failed += 1
                result.errors.append(f"{exercise.exercise_id}: {exc}")
                self._store.mark_failed(exercise.exercise_id, str(exc))
                logger.warning(
                    "Failed to download Polar exercise %s: %s", exercise.exercise_id, exc
                )

        return result

    def _write_file(self, exercise_id: str, content: bytes) -> Path:
        path = self._raw_data_dir / f"{exercise_id}.{self._file_format}"
        path.write_bytes(content)
        return path
