"""Unit tests for the Polar OAuth2 client and the token manager."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.core.etl.polar_oauth import (
    PolarOAuthClient,
    PolarOAuthError,
    TokenManager,
)
from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore

Handler = Callable[[httpx2.Request], httpx2.Response]

_TOKEN_RESPONSE = {
    "access_token": "access-123",
    "refresh_token": "refresh-456",
    "token_type": "bearer",
    "expires_in": 3600,
    "scope": "accesslink.read_all",
}


def _config() -> PolarConfig:
    return PolarConfig(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:8000/auth/callback",
    )


def _client(handler: Handler) -> PolarOAuthClient:
    return PolarOAuthClient(
        _config(), client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )


def test_build_authorize_url_includes_required_params() -> None:
    url = PolarOAuthClient(_config()).build_authorize_url("the-state")

    assert url.startswith("https://flow.polar.com/oauth2/authorization?")
    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fcallback" in url
    assert "scope=accesslink.read_all" in url
    assert "state=the-state" in url


def test_exchange_code_parses_tokens() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/oauth2/token")
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=the-code" in body
        return httpx2.Response(200, json=_TOKEN_RESPONSE, headers={"x_user_id": "999"})

    tokens = _client(handler).exchange_code("the-code")

    assert tokens.access_token == "access-123"
    assert tokens.refresh_token == "refresh-456"
    assert tokens.user_id == "999"
    assert tokens.is_valid()


def test_token_request_uses_basic_auth() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["authorization"].startswith("Basic ")
        return httpx2.Response(200, json=_TOKEN_RESPONSE)

    tokens = _client(handler).exchange_code("the-code")

    assert tokens.access_token == "access-123"


def test_refresh_keeps_original_refresh_token_when_absent() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "new-access", "expires_in": 3600})

    tokens = _client(handler).refresh("keep-me")

    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "keep-me"


def test_token_error_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, text="invalid_grant")

    with pytest.raises(PolarOAuthError, match="token request failed"):
        _client(handler).exchange_code("bad-code")


def test_register_user_returns_polar_user_id() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path.endswith("/users")
        assert request.headers["authorization"] == "Bearer access-123"
        return httpx2.Response(200, json={"polar-user-id": "42", "member-id": "user"})

    assert _client(handler).register_user("access-123") == "42"


def test_register_user_conflict_is_ignored() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(409, text="already registered")

    assert _client(handler).register_user("access-123") == ""


def test_register_user_error_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, text="boom")

    with pytest.raises(PolarOAuthError, match="registration failed"):
        _client(handler).register_user("access-123")


def _expired_tokens() -> OAuthTokens:
    return OAuthTokens(
        access_token="old-access",
        refresh_token="refresh-456",
        user_id="user-1",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )


def test_manager_returns_none_when_empty(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    manager = TokenManager(PolarOAuthClient(_config()), store)

    assert manager.get_valid_tokens() is None
    assert manager.force_refresh() is None


def test_manager_refreshes_expired_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(_expired_tokens())

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "new-access", "expires_in": 3600})

    manager = TokenManager(_client(handler), store)
    tokens = manager.get_valid_tokens()

    assert tokens is not None
    assert tokens.access_token == "new-access"
    assert tokens.user_id == "user-1"
    stored = store.get()
    assert stored is not None
    assert stored.access_token == "new-access"


def test_manager_skips_refresh_for_valid_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(
        OAuthTokens(
            access_token="still-good",
            refresh_token="refresh-456",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("Refresh should not have been called")

    manager = TokenManager(_client(handler), store)
    tokens = manager.get_valid_tokens()

    assert tokens is not None
    assert tokens.access_token == "still-good"
