"""Unit tests for the DuckDB-backed ingest log store."""

from __future__ import annotations

from pathlib import Path

from athlete_stress_sim.core.storage.ingest_store import IngestStatus, IngestStore


def test_is_downloaded_is_false_when_empty(tmp_path: Path) -> None:
    store = IngestStore(tmp_path / "ingest.duckdb")

    assert not store.is_downloaded("abc")
    assert store.get("abc") is None


def test_mark_downloaded_then_is_downloaded(tmp_path: Path) -> None:
    store = IngestStore(tmp_path / "ingest.duckdb")

    store.mark_downloaded("abc", "data/raw/abc.fit", "fit")

    assert store.is_downloaded("abc")
    record = store.get("abc")
    assert record is not None
    assert record.status is IngestStatus.DOWNLOADED
    assert record.file_path == "data/raw/abc.fit"
    assert record.file_format == "fit"


def test_mark_failed_is_not_downloaded(tmp_path: Path) -> None:
    store = IngestStore(tmp_path / "ingest.duckdb")

    store.mark_failed("abc", "boom")

    assert not store.is_downloaded("abc")
    record = store.get("abc")
    assert record is not None
    assert record.status is IngestStatus.FAILED
    assert record.error == "boom"


def test_mark_downloaded_overwrites_failure(tmp_path: Path) -> None:
    store = IngestStore(tmp_path / "ingest.duckdb")
    store.mark_failed("abc", "boom")

    store.mark_downloaded("abc", "data/raw/abc.fit", "fit")

    assert store.is_downloaded("abc")


def test_count_by_status_and_list_all(tmp_path: Path) -> None:
    store = IngestStore(tmp_path / "ingest.duckdb")
    store.mark_downloaded("a", "data/raw/a.fit", "fit")
    store.mark_downloaded("b", "data/raw/b.fit", "fit")
    store.mark_failed("c", "boom")

    counts = store.count_by_status()

    assert counts == {"downloaded": 2, "failed": 1}
    assert len(store.list_all()) == 3


def test_persists_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest.duckdb"
    IngestStore(db_path).mark_downloaded("abc", "data/raw/abc.fit", "fit")

    assert IngestStore(db_path).is_downloaded("abc")
