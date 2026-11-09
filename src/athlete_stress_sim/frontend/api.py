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
from pydantic import TypeAdapter

from athlete_stress_sim.backend.schemas.exercises import ExerciseOut, RpeInput
from athlete_stress_sim.backend.schemas.ingest import SyncResponse
from athlete_stress_sim.backend.schemas.metrics import (
    AcwrResponse,
    BanisterSeriesResponse,
    CalibrationResponse,
    DecouplingResponse,
    PlannedSession,
    RunningBaselineResponse,
    TaperPlanRequest,
    TaperPlanResponse,
    TaperSimulationRequest,
    TaperSimulationResponse,
)
from athlete_stress_sim.backend.schemas.prediction import (
    EffortOut,
    RacePredictionRequest,
    RacePredictionResponse,
)
from athlete_stress_sim.core.models.banister import BanisterParams

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

    def get_exercises(self, kind: str = "run") -> list[ExerciseOut]:
        """Fetch the persisted exercises, optionally filtered by ``kind``."""
        payload = self._get(f"/exercises?kind={kind}")
        return TypeAdapter(list[ExerciseOut]).validate_python(payload)

    def sync(self) -> SyncResponse:
        """Ask the backend to download and parse new Polar sessions."""
        return SyncResponse.model_validate(self._post("/sync", {}))

    def set_rpe(self, exercise_id: str, rpe: float) -> ExerciseOut:
        """Record the session-RPE of one exercise."""
        payload = RpeInput(rpe=rpe).model_dump(mode="json")
        return ExerciseOut.model_validate(self._post(f"/exercises/{exercise_id}/rpe", payload))

    def get_decoupling(self, exercise_id: str) -> DecouplingResponse:
        """Fetch the per-kilometre efficiency and aerobic decoupling of an exercise."""
        return DecouplingResponse.model_validate(self._get(f"/metrics/decoupling/{exercise_id}"))

    def get_calibration(self) -> CalibrationResponse:
        """Fetch the calibrated Banister parameters and their validation."""
        return CalibrationResponse.model_validate(self._get("/metrics/calibration"))

    def get_best_efforts(self) -> list[EffortOut]:
        """Fetch the best detected training effort for each reference distance."""
        payload = self._get("/metrics/best-efforts")
        return TypeAdapter(list[EffortOut]).validate_python(payload)

    def predict_race(self, request: RacePredictionRequest) -> RacePredictionResponse:
        """Predict a race time from detected efforts and/or a manual reference."""
        payload = request.model_dump(mode="json")
        return RacePredictionResponse.model_validate(
            self._post("/metrics/race-prediction", payload)
        )

    def get_running_baseline(self) -> RunningBaselineResponse | None:
        """Fetch the recent weekly running volume, or ``None`` without enough data."""
        payload = self._get("/metrics/running-baseline")
        if payload is None:
            return None
        return RunningBaselineResponse.model_validate(payload)

    def post_taper(
        self,
        sessions: list[PlannedSession],
        params: BanisterParams | None = None,
    ) -> TaperSimulationResponse:
        """Project the fitness-fatigue model over the given planned sessions."""
        request = TaperSimulationRequest(sessions=sessions, params=params)
        payload = request.model_dump(mode="json")
        return TaperSimulationResponse.model_validate(self._post("/simulate/taper", payload))

    def post_taper_plan(self, request: TaperPlanRequest) -> TaperPlanResponse:
        """Generate a pre-race taper plan and its projection to race day."""
        payload = request.model_dump(mode="json")
        return TaperPlanResponse.model_validate(self._post("/simulate/taper/plan", payload))

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

    def _post(self, path: str, body: object) -> object:
        url = f"{self._base_url}{path}"
        with self._connection() as client:
            try:
                response = client.post(url, json=body)
            except httpx2.TransportError as exc:
                raise MetricsClientError(f"Metrics API unreachable at {url}: {exc}") from exc
        if response.status_code >= _HTTP_BAD_REQUEST:
            raise MetricsClientError(
                f"Metrics API returned {response.status_code} for {url}: {response.text}"
            )
        payload: object = response.json()
        return payload
