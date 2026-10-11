"""Polar AccessLink REST client (v3) for exercises.

Wraps the user-authenticated endpoints used by the ingestion pipeline:
listing exercises, fetching a summary and downloading the raw FIT/TCX files.
All calls go through a retry helper that backs off on HTTP 429/5xx responses,
honours the ``Retry-After`` header and retries transient transport errors
(connection/TLS timeouts).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx2
from pydantic import BaseModel, Field

from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.core.etl.polar_oauth import TokenManager

_HTTP_BAD_REQUEST = 400
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVER_ERROR = 500
_DEFAULT_TIMEOUT_S = 30.0


class PolarAuthError(RuntimeError):
    """Raised when no valid Polar access token is available."""


class PolarAPIError(RuntimeError):
    """Raised when a Polar AccessLink request fails."""


class PolarExercise(BaseModel):
    """A training session as returned by ``GET /v3/exercises``."""

    exercise_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PolarClient:
    """Client for the Polar AccessLink v3 exercise endpoints.

    Args:
        config: Polar settings (API base URL and credentials).
        token_manager: Provides a valid OAuth2 access token per request.
        client: Optional pre-built ``httpx2.Client`` for tests.
        max_retries: Maximum number of retries after a retryable response/error.
        backoff_base: Base seconds for exponential backoff.
        sleep: Injectable sleep function (tests pass a no-op).
        timeout: Request timeout in seconds (connection/read) for the HTTP client.
    """

    def __init__(
        self,
        config: PolarConfig,
        token_manager: TokenManager,
        *,
        client: httpx2.Client | None = None,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._config = config
        self._token_manager = token_manager
        self._client = client if client is not None else httpx2.Client(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sleep = sleep

    def list_exercises(self) -> list[PolarExercise]:
        """List exercises available in AccessLink (last 30 days)."""
        response = self._request("GET", f"{self._config.api_url}/exercises")
        self._raise_for_status(response, "list exercises")
        payload = response.json()
        items = payload.get("exercises", []) if isinstance(payload, dict) else payload
        return [PolarExercise(exercise_id=str(item["id"]), payload=dict(item)) for item in items]

    def get_exercise(self, exercise_id: str) -> dict[str, Any]:
        """Return the summary of a single exercise."""
        response = self._request("GET", f"{self._config.api_url}/exercises/{exercise_id}")
        self._raise_for_status(response, f"get exercise {exercise_id}")
        result: dict[str, Any] = response.json()
        return result

    def download_exercise_file(self, exercise_id: str, file_format: str = "fit") -> bytes:
        """Download the raw FIT/TCX/GPX file for an exercise."""
        url = f"{self._config.api_url}/exercises/{exercise_id}/{file_format}"
        response = self._request("GET", url)
        self._raise_for_status(response, f"download {file_format} for {exercise_id}")
        return response.content

    def _auth_headers(self) -> dict[str, str]:
        tokens = self._token_manager.get_valid_tokens()
        if tokens is None:
            raise PolarAuthError("No Polar account linked; run /auth/login first.")
        return {"Authorization": f"Bearer {tokens.access_token}"}

    def _request(self, method: str, url: str) -> httpx2.Response:
        headers = self._auth_headers()
        attempt = 0
        while True:
            try:
                response = self._client.request(method, url, headers=headers)
            except httpx2.TransportError as exc:
                if attempt >= self._max_retries:
                    raise PolarAPIError(
                        f"Polar request failed after {attempt + 1} attempts: {exc}"
                    ) from exc
                self._sleep(self._backoff_base * (2.0**attempt))
                attempt += 1
                continue
            if not self._is_retryable(response) or attempt >= self._max_retries:
                return response
            self._sleep(self._retry_delay(response, attempt))
            attempt += 1

    def _is_retryable(self, response: httpx2.Response) -> bool:
        return (
            response.status_code == _HTTP_TOO_MANY_REQUESTS
            or response.status_code >= _HTTP_SERVER_ERROR
        )

    def _retry_delay(self, response: httpx2.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return float(retry_after)
        return self._backoff_base * (2.0**attempt)

    def _raise_for_status(self, response: httpx2.Response, action: str) -> None:
        if response.status_code >= _HTTP_BAD_REQUEST:
            raise PolarAPIError(
                f"Polar failed to {action} ({response.status_code}): {response.text}"
            )
