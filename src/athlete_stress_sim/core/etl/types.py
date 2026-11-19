"""Domain types shared across the ETL pipeline (S4)."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple, Protocol

from pydantic import BaseModel, Field


class RawRecord(BaseModel):
    """A single telemetry record read from a raw FIT file."""

    timestamp: datetime | None = None
    hr: float | None = None
    speed_mps: float | None = None
    cadence: float | None = None
    altitude_m: float | None = None
    distance_m: float | None = None


class Sample(BaseModel):
    """A normalized, validated second-by-second telemetry sample."""

    timestamp: datetime
    elapsed_s: float
    hr: int | None = None
    speed_mps: float | None = None
    cadence: int | None = None
    altitude_m: float | None = None
    distance_m: float | None = None
    is_valid: bool = True


class SampleLike(Protocol):
    """Structural type shared by parsed samples and lightweight storage rows."""

    @property
    def timestamp(self) -> datetime: ...

    @property
    def elapsed_s(self) -> float: ...

    @property
    def hr(self) -> int | None: ...

    @property
    def speed_mps(self) -> float | None: ...

    @property
    def cadence(self) -> int | None: ...

    @property
    def altitude_m(self) -> float | None: ...

    @property
    def distance_m(self) -> float | None: ...

    @property
    def is_valid(self) -> bool: ...


class SampleRow(NamedTuple):
    """Lightweight, unvalidated sample read from DuckDB.

    Used by batch queries to avoid constructing thousands of Pydantic models;
    it satisfies :class:`SampleLike`, so the metric helpers accept it directly.
    """

    timestamp: datetime
    elapsed_s: float
    hr: int | None
    speed_mps: float | None
    cadence: int | None
    altitude_m: float | None
    distance_m: float | None
    is_valid: bool


class SessionMetadata(BaseModel):
    """Session-level summary extracted from the FIT ``session`` message."""

    sport: str = ""
    sub_sport: str = ""
    start_time: datetime | None = None
    duration_s: float | None = None
    distance_m: float | None = None
    calories: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    total_ascent_m: float | None = None
    total_descent_m: float | None = None


class ParsedSession(BaseModel):
    """A parsed FIT session: metadata plus its normalized samples."""

    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
    samples: list[Sample] = Field(default_factory=list)


class Exercise(BaseModel):
    """A persisted exercise summary (row of the ``exercises`` table)."""

    exercise_id: str
    sport: str = ""
    sub_sport: str = ""
    start_time: datetime | None = None
    duration_s: float | None = None
    distance_m: float | None = None
    calories: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    total_ascent_m: float | None = None
    total_descent_m: float | None = None
    file_path: str = ""
