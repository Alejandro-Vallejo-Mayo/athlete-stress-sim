"""Unit tests for the FIT parsing service."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from athlete_stress_sim.core.etl.parse_service import ParseService
from athlete_stress_sim.core.storage.ingest_store import IngestStore
from athlete_stress_sim.core.storage.session_store import SessionStore
from tests.helpers.fit_fixture import RecordSpec, write_activity_fit

_START = datetime(2026, 10, 3, 7, 0, 0)


def _write_fit(path: Path) -> Path:
    records = [
        RecordSpec(
            timestamp=_START + timedelta(seconds=i),
            hr=120 + i,
            speed_mps=2.5,
            cadence=80 + i,
            altitude_m=10.0,
            distance_m=2.5 * i,
        )
        for i in range(3)
    ]
    return write_activity_fit(path, records)


def _stores(tmp_path: Path) -> tuple[IngestStore, SessionStore]:
    return (
        IngestStore(tmp_path / "ingest.duckdb"),
        SessionStore(tmp_path / "sessions.duckdb"),
    )


def test_process_pending_parses_downloaded_file(tmp_path: Path) -> None:
    ingest, sessions = _stores(tmp_path)
    fit_path = _write_fit(tmp_path / "run.fit")
    ingest.mark_downloaded("abc", str(fit_path), "fit")

    result = ParseService(ingest, sessions).process_pending()

    assert result.parsed == 1
    assert result.failed == 0
    assert sessions.has_session("abc")
    assert sessions.count_samples("abc") == 3


def test_process_pending_is_idempotent(tmp_path: Path) -> None:
    ingest, sessions = _stores(tmp_path)
    fit_path = _write_fit(tmp_path / "run.fit")
    ingest.mark_downloaded("abc", str(fit_path), "fit")
    service = ParseService(ingest, sessions)

    service.process_pending()
    second = service.process_pending()

    assert second.parsed == 0
    assert second.skipped == 1
    assert sessions.count_sessions() == 1


def test_process_pending_reports_missing_file(tmp_path: Path) -> None:
    ingest, sessions = _stores(tmp_path)
    ingest.mark_downloaded("abc", str(tmp_path / "missing.fit"), "fit")

    result = ParseService(ingest, sessions).process_pending()

    assert result.parsed == 0
    assert result.failed == 1
    assert result.errors


def test_process_pending_ignores_failed_downloads(tmp_path: Path) -> None:
    ingest, sessions = _stores(tmp_path)
    ingest.mark_failed("abc", "download boom")

    result = ParseService(ingest, sessions).process_pending()

    assert (result.parsed, result.skipped, result.failed) == (0, 0, 0)
