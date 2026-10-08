"""Endpoints to trigger and inspect the catch-up ingestion pipeline.

``POST /sync`` runs the full pipeline: download missing exercises (S3) and parse
them into DuckDB (S4).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from athlete_stress_sim.backend.api.oauth import get_oauth_client, get_token_store
from athlete_stress_sim.backend.config import polar, storage
from athlete_stress_sim.core.etl.parse_service import ParseResult, ParseService
from athlete_stress_sim.core.etl.polar_client import PolarAPIError, PolarAuthError, PolarClient
from athlete_stress_sim.core.etl.polar_oauth import TokenManager
from athlete_stress_sim.core.etl.sync_service import SyncResult, SyncService
from athlete_stress_sim.core.storage.ingest_store import IngestStatus, IngestStore
from athlete_stress_sim.core.storage.session_store import SessionStore
from athlete_stress_sim.core.storage.token_store import TokenStore

router = APIRouter(tags=["ingest"])


@lru_cache(maxsize=1)
def get_ingest_store() -> IngestStore:
    """Provide the shared ingest log store."""
    return IngestStore(storage.db_path)


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    """Provide the shared parsed-session store."""
    return SessionStore(storage.db_path)


@lru_cache(maxsize=1)
def get_sync_service() -> SyncService:
    """Provide the shared catch-up sync service."""
    token_manager = TokenManager(get_oauth_client(), get_token_store())
    client = PolarClient(polar, token_manager)
    return SyncService(client, get_ingest_store(), storage.raw_data_dir)


@lru_cache(maxsize=1)
def get_parse_service() -> ParseService:
    """Provide the shared FIT parsing service."""
    return ParseService(get_ingest_store(), get_session_store())


SyncDep = Annotated[SyncService, Depends(get_sync_service)]
ParseDep = Annotated[ParseService, Depends(get_parse_service)]
IngestStoreDep = Annotated[IngestStore, Depends(get_ingest_store)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
TokenStoreDep = Annotated[TokenStore, Depends(get_token_store)]


def run_ingestion(
    sync_service: SyncService,
    parse_service: ParseService,
    session_store: SessionStore,
    token_store: TokenStore,
) -> dict[str, object]:
    """Run the full download + parse pipeline and return a combined summary."""
    sync_result: SyncResult = sync_service.sync()
    tokens = token_store.get()
    if tokens is not None and tokens.user_id:
        session_store.ensure_athlete(tokens.user_id)
    parse_result: ParseResult = parse_service.process_pending()
    return {"sync": sync_result.model_dump(), "parse": parse_result.model_dump()}


@router.post("/sync")
def run_sync(
    sync_service: SyncDep,
    parse_service: ParseDep,
    session_store: SessionStoreDep,
    token_store: TokenStoreDep,
) -> dict[str, object]:
    """Download and parse every Polar exercise not ingested yet."""
    try:
        return run_ingestion(sync_service, parse_service, session_store, token_store)
    except PolarAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PolarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/sync/status")
def sync_status(
    ingest_store: IngestStoreDep,
    session_store: SessionStoreDep,
) -> dict[str, int]:
    """Return ingest/parse counters."""
    counts = ingest_store.count_by_status()
    downloaded = counts.get(IngestStatus.DOWNLOADED.value, 0)
    failed = counts.get(IngestStatus.FAILED.value, 0)
    return {
        "downloaded": downloaded,
        "failed": failed,
        "total": downloaded + failed,
        "parsed_sessions": session_store.count_sessions(),
    }
