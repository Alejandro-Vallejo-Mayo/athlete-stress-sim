"""Integration tests for the ``/auth`` endpoints with a mocked Polar server."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx2
import pytest
from fastapi.testclient import TestClient

from athlete_stress_sim.backend.api import oauth as oauth_api
from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.backend.main import app
from athlete_stress_sim.core.etl.polar_oauth import PolarOAuthClient
from athlete_stress_sim.core.storage.token_store import TokenStore


def _handler(request: httpx2.Request) -> httpx2.Response:
    if request.url.path.endswith("/oauth2/token"):
        return httpx2.Response(
            200,
            json={
                "access_token": "access-token-value",
                "refresh_token": "refresh-token-value",
                "token_type": "bearer",
                "expires_in": 3600,
                "scope": "accesslink.read_all",
            },
            headers={"x_user_id": "777"},
        )
    if request.url.path.endswith("/users"):
        return httpx2.Response(
            200, json={"polar-user-id": "777", "member-id": "athlete-stress-sim"}
        )
    raise AssertionError(f"Unexpected request: {request.url}")


@pytest.fixture
def store(tmp_path: Path) -> TokenStore:
    return TokenStore(tmp_path / "auth.duckdb")


@pytest.fixture
def client(store: TokenStore) -> Iterator[TestClient]:
    oauth_client = PolarOAuthClient(
        PolarConfig(client_id="cid", client_secret="secret"),
        client=httpx2.Client(transport=httpx2.MockTransport(_handler)),
    )
    app.dependency_overrides[oauth_api.get_oauth_client] = lambda: oauth_client
    app.dependency_overrides[oauth_api.get_token_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login_state(client: TestClient) -> str:
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("https://flow.polar.com/oauth2/authorization?")
    return parse_qs(urlparse(location).query)["state"][0]


def test_status_reports_unauthorized_when_empty(client: TestClient) -> None:
    response = client.get("/auth/status")

    assert response.status_code == 200
    assert response.json() == {"authorized": False}


def test_login_redirects_to_polar_with_state(client: TestClient) -> None:
    state = _login_state(client)

    assert state


def test_callback_rejects_invalid_state(client: TestClient) -> None:
    response = client.get("/auth/callback", params={"code": "abc", "state": "nope"})

    assert response.status_code == 400


def test_callback_links_account_and_persists_tokens(client: TestClient) -> None:
    state = _login_state(client)

    response = client.get("/auth/callback", params={"code": "abc", "state": state})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["user_id"] == "777"

    status = client.get("/auth/status").json()
    assert status["authorized"] is True
    assert status["valid"] is True
    assert status["user_id"] == "777"
    assert status["access_token"] == "acce…alue"


def test_callback_code_cannot_be_replayed(client: TestClient) -> None:
    state = _login_state(client)
    client.get("/auth/callback", params={"code": "abc", "state": state})

    replay = client.get("/auth/callback", params={"code": "abc", "state": state})

    assert replay.status_code == 400


def test_refresh_without_authorization_fails(client: TestClient) -> None:
    response = client.get("/auth/refresh")

    assert response.status_code == 400


def test_refresh_after_authorization_succeeds(client: TestClient) -> None:
    state = _login_state(client)
    client.get("/auth/callback", params={"code": "abc", "state": state})

    response = client.get("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["status"] == "refreshed"
