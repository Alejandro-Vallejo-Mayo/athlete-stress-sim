"""FastAPI backend entry point.

In S1 this is only a *scaffold*: the app starts with a health endpoint. Metrics,
OAuth2 and webhook endpoints arrive in S2-S3 and S10.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from athlete_stress_sim.backend.config import physiology, polar

app = FastAPI(
    title="Athlete Stress Sim",
    version="0.1.0",
    description="Biomechanical Fatigue & Load Management Optimizer",
)


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
