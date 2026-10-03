"""Integration tests for the ``/sync`` endpoints with a mocked Polar server."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api import ingest as ingest_api
from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.polar_client import PolarAuthError, PolarClient
from athlete_stress_sim.core.etl.polar_oauth import PolarOAuthClient, TokenManager
from athlete_stress_sim.core.etl.sync_service import SyncService
from athlete_stress_sim.core.storage.ingest_store import IngestStore
from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore

Handler = Callable[[httpx2.Request], httpx2.Response]


def _config() -> PolarConfig:
    return PolarConfig(client_id="cid", client_secret="secret")


def _token_manager(tmp_path: Path) -> TokenManager:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(
        OAuthTokens(
            access_token="tok",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    return TokenManager(PolarOAuthClient(_config()), store)


def _handler(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/v3/exercises":
        return httpx2.Response(200, json={"exercises": [{"id": "a"}]})
    if request.url.path.endswith("/fit"):
        return httpx2.Response(200, content=b"AAA")
    raise AssertionError(request.url)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = IngestStore(tmp_path / "ingest.duckdb")
    polar_client = PolarClient(
        _config(),
        _token_manager(tmp_path),
        client=httpx2.Client(transport=httpx2.MockTransport(_handler)),
        sleep=lambda _: None,
    )
    service = SyncService(polar_client, store, tmp_path / "raw")
    app.dependency_overrides[ingest_api.get_sync_service] = lambda: service
    app.dependency_overrides[ingest_api.get_ingest_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_run_sync_downloads_and_reports(client: TestClient) -> None:
    response = client.post("/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["listed"] == 1
    assert body["downloaded"] == 1
    assert body["failed"] == 0


def test_sync_status_reports_counts(client: TestClient) -> None:
    client.post("/sync")

    response = client.get("/sync/status")

    assert response.status_code == 200
    assert response.json() == {"downloaded": 1, "failed": 0, "total": 1}


def test_run_sync_returns_400_when_not_linked() -> None:
    class _UnlinkedSync:
        def sync(self) -> object:
            raise PolarAuthError("No Polar account linked")

    unlinked = _UnlinkedSync()
    app.dependency_overrides[ingest_api.get_sync_service] = lambda: unlinked
    try:
        response = TestClient(app).post("/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
