"""FastAPI backend entry point.

S1 scaffold, the S2 Polar OAuth2 router, the S3 catch-up ingestion sync and the
S10 metrics/simulation endpoints (TRIMP, ACWR, Banister, ``/simulate``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from athlete_stress_sim.backend.api.exercises import router as exercises_router
from athlete_stress_sim.backend.api.ingest import (
    get_parse_service,
    get_session_store,
    get_sync_service,
    run_ingestion,
)
from athlete_stress_sim.backend.api.ingest import router as ingest_router
from athlete_stress_sim.backend.api.metrics import router as metrics_router
from athlete_stress_sim.backend.api.metrics import simulate_router
from athlete_stress_sim.backend.api.oauth import get_token_store
from athlete_stress_sim.backend.api.oauth import router as oauth_router
from athlete_stress_sim.backend.config import physiology, polar
from athlete_stress_sim.core.etl.polar_client import PolarAuthError

logger = logging.getLogger(__name__)


def _startup_sync() -> None:
    """Run one catch-up sync + parse, logging instead of raising on failure."""
    try:
        result = run_ingestion(
            get_sync_service(),
            get_parse_service(),
            get_session_store(),
            get_token_store(),
        )
        logger.info("Startup ingestion finished: %s", result)
    except PolarAuthError:
        logger.info("Startup ingestion skipped: no Polar account linked yet.")
    except Exception:  # noqa: BLE001
        logger.exception("Startup ingestion failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Kick off a catch-up sync in the background when the app starts."""
    task: asyncio.Task[None] | None = None
    if polar.sync_on_startup:
        task = asyncio.create_task(asyncio.to_thread(_startup_sync))
    yield
    if task is not None and not task.done():
        task.cancel()


app = FastAPI(
    title="Athlete Stress Sim",
    version="0.1.0",
    description="Biomechanical Fatigue & Load Management Optimizer",
    lifespan=lifespan,
)

app.include_router(oauth_router)
app.include_router(ingest_router)
app.include_router(exercises_router)
app.include_router(metrics_router)
app.include_router(simulate_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return the backend liveness status."""
    return {"status": "ok"}


@app.get("/config/physiology", tags=["system"])
def read_physiology() -> dict[str, float]:
    """Expose the active physiological constants (no credentials)."""
    return physiology.model_dump()


def main() -> None:
    """Run the development server as the ``athlete-stress-sim`` console script."""
    uvicorn.run("athlete_stress_sim.backend.main:app", host="0.0.0.0", port=8000, reload=True)


__all__ = ["app", "main", "polar"]
