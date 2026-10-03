"""Integration tests for the ``/sync`` endpoints with a mocked Polar server."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx2
import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api import ingest as ingest_api
from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.parse_service import ParseService
from athlete_stress_sim.core.etl.polar_client import PolarAuthError, PolarClient
from athlete_stress_sim.core.etl.polar_oauth import PolarOAuthClient, TokenManager
from athlete_stress_sim.core.etl.sync_service import SyncResult, SyncService
from athlete_stress_sim.core.storage.ingest_store import IngestStore
from athlete_stress_sim.core.storage.session_store import SessionStore
from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore
from tests.helpers.fit_fixture import RecordSpec, build_activity_fit

Handler = Callable[[httpx2.Request], httpx2.Response]

_START = datetime(2026, 10, 3, 7, 0, 0)
_FIT_BYTES = build_activity_fit(
    [
        RecordSpec(
            timestamp=_START + timedelta(seconds=i),
            hr=120 + i,
            speed_mps=2.5,
            cadence=80,
            altitude_m=10.0,
            distance_m=2.5 * i,
        )
        for i in range(3)
    ]
)


class _SyncLike(Protocol):
    def sync(self) -> SyncResult: ...


def _config() -> PolarConfig:
    return PolarConfig(client_id="cid", client_secret="secret")


def _handler(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/v3/exercises":
        return httpx2.Response(200, json={"exercises": [{"id": "a"}]})
    if request.url.path.endswith("/fit"):
        return httpx2.Response(200, content=_FIT_BYTES)
    raise AssertionError(request.url)


def _install_overrides(
    tmp_path: Path,
    sync_service: _SyncLike,
) -> tuple[IngestStore, SessionStore, TokenStore]:
    ingest = IngestStore(tmp_path / "ingest.duckdb")
    sessions = SessionStore(tmp_path / "sessions.duckdb")
    tokens = TokenStore(tmp_path / "tokens.duckdb")
    tokens.save(
        OAuthTokens(
            access_token="tok",
            user_id="777",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    app.dependency_overrides[ingest_api.get_sync_service] = lambda: sync_service
    app.dependency_overrides[ingest_api.get_parse_service] = lambda: ParseService(ingest, sessions)
    app.dependency_overrides[ingest_api.get_ingest_store] = lambda: ingest
    app.dependency_overrides[ingest_api.get_session_store] = lambda: sessions
    app.dependency_overrides[ingest_api.get_token_store] = lambda: tokens
    return ingest, sessions, tokens


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    token_store = TokenStore(tmp_path / "sync-tokens.duckdb")
    token_store.save(
        OAuthTokens(
            access_token="tok",
            user_id="777",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    polar_client = PolarClient(
        _config(),
        TokenManager(PolarOAuthClient(_config()), token_store),
        client=httpx2.Client(transport=httpx2.MockTransport(_handler)),
        sleep=lambda _: None,
    )
    ingest = IngestStore(tmp_path / "ingest.duckdb")
    sync_service = SyncService(polar_client, ingest, tmp_path / "raw")
    _install_overrides(tmp_path, sync_service)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_run_sync_downloads_and_parses(client: TestClient) -> None:
    response = client.post("/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["sync"]["listed"] == 1
    assert body["sync"]["downloaded"] == 1
    assert body["parse"]["parsed"] == 1


def test_run_sync_persists_session_and_athlete(
    client: TestClient,
    tmp_path: Path,
) -> None:
    client.post("/sync")

    sessions = SessionStore(tmp_path / "sessions.duckdb")
    assert sessions.has_session("a")
    assert sessions.count_samples("a") == 3
    assert sessions.get_athlete() == "777"


def test_sync_status_reports_counts(client: TestClient) -> None:
    client.post("/sync")

    response = client.get("/sync/status")

    assert response.status_code == 200
    assert response.json() == {
        "downloaded": 1,
        "failed": 0,
        "total": 1,
        "parsed_sessions": 1,
    }


def test_run_sync_returns_400_when_not_linked(tmp_path: Path) -> None:
    class _UnlinkedSync:
        def sync(self) -> SyncResult:
            raise PolarAuthError("No Polar account linked")

    _install_overrides(tmp_path, _UnlinkedSync())
    try:
        response = TestClient(app).post("/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
