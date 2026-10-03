"""Unit tests for the Polar AccessLink v3 exercise client."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.core.etl.polar_client import (
    PolarAPIError,
    PolarAuthError,
    PolarClient,
)
from athlete_stress_sim.core.etl.polar_oauth import PolarOAuthClient, TokenManager
from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore

Handler = Callable[[httpx2.Request], httpx2.Response]
SleepFn = Callable[[float], None]


def _config() -> PolarConfig:
    return PolarConfig(client_id="cid", client_secret="secret")


def _token_manager(tmp_path: Path) -> TokenManager:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(
        OAuthTokens(
            access_token="access-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    return TokenManager(PolarOAuthClient(_config()), store)


def _client(
    handler: Handler,
    tmp_path: Path,
    sleep: SleepFn = lambda _: None,
    max_retries: int = 4,
) -> PolarClient:
    return PolarClient(
        _config(),
        _token_manager(tmp_path),
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        max_retries=max_retries,
        sleep=sleep,
    )


def test_list_exercises_returns_ids(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v3/exercises"
        assert request.headers["authorization"] == "Bearer access-token"
        return httpx2.Response(200, json={"exercises": [{"id": "a"}, {"id": "b"}]})

    exercises = _client(handler, tmp_path).list_exercises()

    assert [exercise.exercise_id for exercise in exercises] == ["a", "b"]
    assert exercises[0].payload == {"id": "a"}


def test_list_exercises_accepts_bare_list(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"id": "a"}])

    assert _client(handler, tmp_path).list_exercises()[0].exercise_id == "a"


def test_get_exercise_returns_payload(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"id": "a", "sport": "RUNNING"})

    assert _client(handler, tmp_path).get_exercise("a")["sport"] == "RUNNING"


def test_download_exercise_file_returns_bytes(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v3/exercises/a/fit"
        return httpx2.Response(200, content=b"FITDATA")

    assert _client(handler, tmp_path).download_exercise_file("a") == b"FITDATA"


def test_raises_api_error_on_404(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(404, text="not found")

    with pytest.raises(PolarAPIError, match="list exercises"):
        _client(handler, tmp_path).list_exercises()


def test_retries_on_429_and_honours_retry_after(tmp_path: Path) -> None:
    calls = {"n": 0}
    delays: list[float] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx2.Response(429, headers={"Retry-After": "7"})
        return httpx2.Response(200, json={"exercises": []})

    client = _client(handler, tmp_path, sleep=delays.append)

    assert client.list_exercises() == []
    assert calls["n"] == 2
    assert delays == [7.0]


def test_retries_on_5xx(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx2.Response(503)
        return httpx2.Response(200, json={"exercises": []})

    assert _client(handler, tmp_path).list_exercises() == []
    assert calls["n"] == 3


def test_gives_up_after_max_retries(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503, text="down")

    with pytest.raises(PolarAPIError, match="list exercises"):
        _client(handler, tmp_path, max_retries=2).list_exercises()


def test_raises_auth_error_without_tokens(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("No HTTP call should be made without a token")

    manager = TokenManager(PolarOAuthClient(_config()), TokenStore(tmp_path / "empty.duckdb"))
    client = PolarClient(
        _config(),
        manager,
        client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )

    with pytest.raises(PolarAuthError):
        client.list_exercises()
