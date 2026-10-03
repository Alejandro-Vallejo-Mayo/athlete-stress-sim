"""Parse downloaded FIT files and persist them into DuckDB (S4)."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from athlete_stress_sim.core.etl.fit_parser import FITParser
from athlete_stress_sim.core.storage.ingest_store import IngestStatus, IngestStore
from athlete_stress_sim.core.storage.session_store import SessionStore

logger = logging.getLogger(__name__)


class ParseResult(BaseModel):
    """Summary of one parsing pass."""

    parsed: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class ParseService:
    """Parse every downloaded-but-unparsed exercise into DuckDB.

    Args:
        ingest_store: Ingest log used to discover downloaded files.
        session_store: Store where parsed sessions are persisted.
        parser: FIT parser (injectable for tests).
    """

    def __init__(
        self,
        ingest_store: IngestStore,
        session_store: SessionStore,
        parser: FITParser | None = None,
    ) -> None:
        self._ingest = ingest_store
        self._sessions = session_store
        self._parser = parser or FITParser()

    def process_pending(self) -> ParseResult:
        """Parse and persist all downloaded files that are not parsed yet."""
        result = ParseResult()
        for record in self._ingest.list_all():
            if record.status is not IngestStatus.DOWNLOADED:
                continue
            if self._sessions.has_session(record.exercise_id):
                result.skipped += 1
                continue

            path = Path(record.file_path) if record.file_path else None
            if path is None or not path.exists():
                result.failed += 1
                result.errors.append(f"{record.exercise_id}: file not found ({record.file_path!r})")
                continue

            try:
                session = self._parser.parse(path)
                self._sessions.save_session(record.exercise_id, session, str(path))
                result.parsed += 1
                logger.info(
                    "Parsed Polar exercise %s (%d samples)",
                    record.exercise_id,
                    len(session.samples),
                )
            except Exception as exc:  # noqa: BLE001
                result.failed += 1
                result.errors.append(f"{record.exercise_id}: {exc}")
                logger.warning("Failed to parse Polar exercise %s: %s", record.exercise_id, exc)

        return result
