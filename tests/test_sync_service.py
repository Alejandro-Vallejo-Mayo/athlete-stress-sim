"""Unit tests for the catch-up sync service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.core.etl.polar_client import PolarAuthError, PolarClient
from athlete_stress_sim.core.etl.polar_oauth import PolarOAuthClient, TokenManager
from athlete_stress_sim.core.etl.sync_service import SyncService
from athlete_stress_sim.core.storage.ingest_store import IngestStatus, IngestStore
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


def _service(handler: Handler, tmp_path: Path, max_retries: int = 4) -> SyncService:
    client = PolarClient(
        _config(),
        _token_manager(tmp_path),
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        max_retries=max_retries,
        sleep=lambda _: None,
    )
    store = IngestStore(tmp_path / "ingest.duckdb")
    return SyncService(client, store, tmp_path / "raw")


def test_sync_downloads_new_exercises(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v3/exercises":
            return httpx2.Response(200, json={"exercises": [{"id": "a"}, {"id": "b"}]})
        if request.url.path == "/v3/exercises/a/fit":
            return httpx2.Response(200, content=b"AAA")
        if request.url.path == "/v3/exercises/b/fit":
            return httpx2.Response(200, content=b"BBB")
        raise AssertionError(request.url)

    result = _service(handler, tmp_path).sync()

    assert (result.listed, result.downloaded, result.skipped, result.failed) == (2, 2, 0, 0)
    assert (tmp_path / "raw" / "a.fit").read_bytes() == b"AAA"
    assert (tmp_path / "raw" / "b.fit").read_bytes() == b"BBB"


def test_sync_is_idempotent(tmp_path: Path) -> None:
    downloads = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v3/exercises":
            return httpx2.Response(200, json={"exercises": [{"id": "a"}]})
        if request.url.path.endswith("/fit"):
            downloads["n"] += 1
            return httpx2.Response(200, content=b"AAA")
        raise AssertionError(request.url)

    service = _service(handler, tmp_path)
    first = service.sync()
    second = service.sync()

    assert first.downloaded == 1
    assert second.downloaded == 0
    assert second.skipped == 1
    assert downloads["n"] == 1


def test_sync_records_failures(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v3/exercises":
            return httpx2.Response(200, json={"exercises": [{"id": "a"}]})
        return httpx2.Response(500, text="boom")

    result = _service(handler, tmp_path, max_retries=1).sync()

    assert result.failed == 1
    assert result.downloaded == 0
    assert result.errors
    record = IngestStore(tmp_path / "ingest.duckdb").get("a")
    assert record is not None
    assert record.status is IngestStatus.FAILED


def test_sync_propagates_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("No HTTP call should be made without a token")

    manager = TokenManager(PolarOAuthClient(_config()), TokenStore(tmp_path / "empty.duckdb"))
    client = PolarClient(
        _config(),
        manager,
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    service = SyncService(client, IngestStore(tmp_path / "ingest.duckdb"), tmp_path / "raw")

    with pytest.raises(PolarAuthError):
        service.sync()
