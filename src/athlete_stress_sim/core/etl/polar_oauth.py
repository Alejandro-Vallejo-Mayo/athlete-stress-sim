"""Polar AccessLink OAuth2 client (Authorization Code flow).

Implements the confidential-client flow: the user is redirected to Polar, the
authorization code is exchanged for tokens using ``client_id``/``client_secret``
(HTTP Basic auth) and the user is registered so their data becomes accessible.
PKCE is not used because AccessLink is a confidential client (see S2 notes).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx2

from athlete_stress_sim.backend.config import PolarConfig
from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore

_HTTP_BAD_REQUEST = 400
_HTTP_CONFLICT = 409


class PolarOAuthError(RuntimeError):
    """Raised when a Polar OAuth2 HTTP exchange fails."""


class PolarOAuthClient:
    """Client for the Polar AccessLink Authorization Code flow.

    Args:
        config: Polar settings (client id/secret, endpoints, redirect URI).
        client: Optional pre-built ``httpx2.Client`` for tests.
    """

    def __init__(self, config: PolarConfig, client: httpx2.Client | None = None) -> None:
        self._config = config
        self._client = client

    def build_authorize_url(self, state: str) -> str:
        """Build the Polar authorization URL the user must be redirected to."""
        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "scope": self._config.scope,
            "state": state,
        }
        return f"{self._config.authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthTokens:
        """Exchange an authorization code for an access/refresh token set."""
        return self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._config.redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> OAuthTokens:
        """Obtain a new access token using a refresh token."""
        return self._post_token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            fallback_refresh=refresh_token,
        )

    def register_user(self, access_token: str) -> str:
        """Register the authorized user in AccessLink.

        Returns:
            The Polar user id, or an empty string if the user was already
            registered (HTTP 409).
        """
        with self._client_context() as client:
            response = client.post(
                f"{self._config.api_url}/users",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"member-id": self._config.member_id},
            )
        if response.status_code == _HTTP_CONFLICT:
            return ""
        if response.status_code >= _HTTP_BAD_REQUEST:
            raise PolarOAuthError(
                f"Polar user registration failed ({response.status_code}): {response.text}"
            )
        payload = response.json()
        return str(payload.get("polar-user-id", ""))

    def _post_token(self, data: dict[str, str], fallback_refresh: str = "") -> OAuthTokens:
        with self._client_context() as client:
            response = client.post(
                self._config.token_url,
                data=data,
                auth=httpx2.BasicAuth(self._config.client_id, self._config.client_secret),
            )
        if response.status_code >= _HTTP_BAD_REQUEST:
            raise PolarOAuthError(
                f"Polar token request failed ({response.status_code}): {response.text}"
            )
        payload = response.json()
        expires_in = int(payload.get("expires_in", 0))
        user_id = response.headers.get("x_user_id", "") or str(payload.get("x_user_id", ""))
        return OAuthTokens(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload.get("refresh_token", fallback_refresh)),
            token_type=str(payload.get("token_type", "Bearer")),
            scope=str(payload.get("scope", self._config.scope)),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )

    @contextmanager
    def _client_context(self) -> Iterator[httpx2.Client]:
        if self._client is not None:
            yield self._client
        else:
            with httpx2.Client() as client:
                yield client


class TokenManager:
    """Keep a valid Polar access token, refreshing it when it is about to expire.

    Args:
        oauth: Client used to refresh tokens.
        store: Persistence for the active token set.
        refresh_margin_seconds: Refresh when the token expires within this window.
    """

    def __init__(
        self,
        oauth: PolarOAuthClient,
        store: TokenStore,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self._oauth = oauth
        self._store = store
        self._margin = refresh_margin_seconds

    def get_valid_tokens(self) -> OAuthTokens | None:
        """Return valid tokens, refreshing them in place when necessary."""
        tokens = self._store.get()
        if tokens is None:
            return None
        if tokens.is_valid(self._margin) or not tokens.refresh_token:
            return tokens
        return self._refresh(tokens)

    def force_refresh(self) -> OAuthTokens | None:
        """Refresh the stored tokens unconditionally, if a refresh token exists."""
        tokens = self._store.get()
        if tokens is None or not tokens.refresh_token:
            return None
        return self._refresh(tokens)

    def _refresh(self, tokens: OAuthTokens) -> OAuthTokens:
        refreshed = self._oauth.refresh(tokens.refresh_token)
        if not refreshed.user_id:
            refreshed.user_id = tokens.user_id
        self._store.save(refreshed)
        return refreshed
