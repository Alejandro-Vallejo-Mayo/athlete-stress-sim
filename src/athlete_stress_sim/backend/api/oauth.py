"""Polar OAuth2 endpoints: link the account and manage the token lifecycle."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from athlete_stress_sim.backend.config import polar, storage
from athlete_stress_sim.core.etl.polar_oauth import (
    PolarOAuthClient,
    TokenManager,
)
from athlete_stress_sim.core.storage.token_store import TokenStore

router = APIRouter(prefix="/auth", tags=["auth"])

_MIN_MASKABLE_SECRET_LENGTH = 8


class StateStore:
    """In-memory, single-use store for OAuth2 ``state`` values (CSRF protection)."""

    def __init__(self, ttl_seconds: float = 600.0) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._states: dict[str, datetime] = {}

    def issue(self) -> str:
        """Create and remember a new opaque state value."""
        state = secrets.token_urlsafe(32)
        self._states[state] = datetime.now(UTC) + self._ttl
        return state

    def consume(self, state: str) -> bool:
        """Validate and invalidate a state value."""
        expiry = self._states.pop(state, None)
        return expiry is not None and datetime.now(UTC) < expiry


_states = StateStore()


@lru_cache(maxsize=1)
def get_token_store() -> TokenStore:
    """Provide the shared token store."""
    return TokenStore(storage.db_path)


@lru_cache(maxsize=1)
def get_oauth_client() -> PolarOAuthClient:
    """Provide the shared Polar OAuth2 client."""
    return PolarOAuthClient(polar)


OAuthDep = Annotated[PolarOAuthClient, Depends(get_oauth_client)]
StoreDep = Annotated[TokenStore, Depends(get_token_store)]


def _mask(secret: str) -> str:
    if len(secret) <= _MIN_MASKABLE_SECRET_LENGTH:
        return "…"
    return f"{secret[:4]}…{secret[-4:]}"


@router.get("/login")
def login(oauth: OAuthDep) -> RedirectResponse:
    """Redirect the user to Polar to authorize this application."""
    state = _states.issue()
    return RedirectResponse(oauth.build_authorize_url(state))


@router.get("/callback")
def callback(
    oauth: OAuthDep,
    store: StoreDep,
    code: Annotated[str, Query(description="Authorization code returned by Polar.")],
    state: Annotated[str, Query(description="Opaque CSRF state issued by /auth/login.")],
) -> dict[str, object]:
    """Handle the OAuth2 redirect: exchange the code and register the user."""
    if not _states.consume(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    tokens = oauth.exchange_code(code)
    polar_user_id = oauth.register_user(tokens.access_token)
    if polar_user_id and not tokens.user_id:
        tokens.user_id = polar_user_id
    store.save(tokens)
    return {
        "status": "ok",
        "user_id": tokens.user_id,
        "expires_at": tokens.expires_at.isoformat(),
    }


@router.get("/status")
def status(store: StoreDep) -> dict[str, object]:
    """Report whether a Polar account is linked and its token state."""
    tokens = store.get()
    if tokens is None:
        return {"authorized": False}
    return {
        "authorized": True,
        "user_id": tokens.user_id,
        "valid": tokens.is_valid(),
        "expires_at": tokens.expires_at.isoformat(),
        "access_token": _mask(tokens.access_token),
    }


@router.get("/refresh")
def refresh_tokens(oauth: OAuthDep, store: StoreDep) -> dict[str, object]:
    """Force a token refresh using the stored refresh token."""
    tokens = TokenManager(oauth, store).force_refresh()
    if tokens is None:
        raise HTTPException(
            status_code=400,
            detail="No refresh token available; run /auth/login first.",
        )
    return {"status": "refreshed", "expires_at": tokens.expires_at.isoformat()}
