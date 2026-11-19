"""Response models for the ingestion endpoints (``S14``)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SyncSummary(BaseModel):
    """Summary of one catch-up synchronization run."""

    listed: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class ParseSummary(BaseModel):
    """Summary of one FIT parsing pass."""

    parsed: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """Combined download and parse result returned by ``POST /sync``."""

    sync: SyncSummary
    parse: ParseSummary
