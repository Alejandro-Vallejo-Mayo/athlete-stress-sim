"""Endpoints to trigger and inspect the catch-up ingestion sync."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from athlete_stress_sim.backend.api.oauth import get_oauth_client, get_token_store
from athlete_stress_sim.backend.config import polar, storage
from athlete_stress_sim.core.etl.polar_client import PolarAuthError, PolarClient
from athlete_stress_sim.core.etl.polar_oauth import TokenManager
from athlete_stress_sim.core.etl.sync_service import SyncResult, SyncService
from athlete_stress_sim.core.storage.ingest_store import IngestStatus, IngestStore

router = APIRouter(tags=["ingest"])


@lru_cache(maxsize=1)
def get_ingest_store() -> IngestStore:
    """Provide the shared ingest log store."""
    return IngestStore(storage.db_path)


@lru_cache(maxsize=1)
def get_sync_service() -> SyncService:
    """Provide the shared catch-up sync service."""
    token_manager = TokenManager(get_oauth_client(), get_token_store())
    client = PolarClient(polar, token_manager)
    return SyncService(client, get_ingest_store(), storage.raw_data_dir)


SyncDep = Annotated[SyncService, Depends(get_sync_service)]
StoreDep = Annotated[IngestStore, Depends(get_ingest_store)]


@router.post("/sync")
def run_sync(service: SyncDep) -> SyncResult:
    """Download every Polar exercise not ingested yet."""
    try:
        return service.sync()
    except PolarAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sync/status")
def sync_status(store: StoreDep) -> dict[str, int]:
    """Return how many exercises are ingested and how many failed."""
    counts = store.count_by_status()
    downloaded = counts.get(IngestStatus.DOWNLOADED.value, 0)
    failed = counts.get(IngestStatus.FAILED.value, 0)
    return {"downloaded": downloaded, "failed": failed, "total": downloaded + failed}
