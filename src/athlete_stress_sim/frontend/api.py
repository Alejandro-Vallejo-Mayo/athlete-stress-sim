"""HTTP client for the backend metrics API consumed by the dashboard (S11).

The dashboard is a separate service from the API (see ``docker/docker-compose.yml``),
so it fetches the aggregated metrics over HTTP instead of reading DuckDB directly.
This module deliberately does not import Dash, keeping it unit-testable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import httpx2

from athlete_stress_sim.backend.schemas.metrics import AcwrResponse, BanisterSeriesResponse

DEFAULT_API_URL = "http://localhost:8000"
_HTTP_BAD_REQUEST = 400


class MetricsClientError(RuntimeError):
    """Raised when the backend metrics API is unreachable or returns an error."""


class MetricsClient:
    """Minimal client over the backend metrics endpoints.

    Args:
        base_url: Backend base URL; falls back to the ``API_URL`` environment
            variable and then to ``http://localhost:8000``.
        client: Optional pre-built ``httpx2.Client`` (tests inject a ``MockTransport``).
    """

    def __init__(self, base_url: str | None = None, *, client: httpx2.Client | None = None) -> None:
        configured = base_url or os.environ.get("API_URL") or DEFAULT_API_URL
        self._base_url = configured.rstrip("/")
        self._client = client

    def get_banister(self) -> BanisterSeriesResponse:
        """Fetch the fitness-fatigue series from the backend."""
        return BanisterSeriesResponse.model_validate(self._get("/metrics/banister"))

    def get_acwr(self) -> AcwrResponse:
        """Fetch the daily acute:chronic workload ratio series from the backend."""
        return AcwrResponse.model_validate(self._get("/metrics/acwr"))

    @contextmanager
    def _connection(self) -> Iterator[httpx2.Client]:
        if self._client is not None:
            yield self._client
        else:
            with httpx2.Client() as client:
                yield client

    def _get(self, path: str) -> object:
        url = f"{self._base_url}{path}"
        with self._connection() as client:
            try:
                response = client.get(url)
            except httpx2.TransportError as exc:
                raise MetricsClientError(f"Metrics API unreachable at {url}: {exc}") from exc
        if response.status_code >= _HTTP_BAD_REQUEST:
            raise MetricsClientError(
                f"Metrics API returned {response.status_code} for {url}: {response.text}"
            )
        payload: object = response.json()
        return payload
