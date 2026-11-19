"""Unit tests for the DuckDB-backed token store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from athlete_stress_sim.core.storage.token_store import OAuthTokens, TokenStore


def _tokens(user_id: str = "user-1", access: str = "access-1") -> OAuthTokens:
    return OAuthTokens(
        access_token=access,
        refresh_token="refresh-1",
        token_type="bearer",
        scope="accesslink.read_all",
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def test_get_returns_none_when_empty(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")

    assert store.get() is None


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    tokens = _tokens()

    store.save(tokens)
    stored = store.get()

    assert stored is not None
    assert stored.access_token == tokens.access_token
    assert stored.refresh_token == tokens.refresh_token
    assert stored.user_id == tokens.user_id
    assert stored.scope == tokens.scope
    assert stored.expires_at.replace(microsecond=0) == tokens.expires_at.replace(microsecond=0)


def test_save_replaces_previous_token_for_same_user(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(_tokens(access="first"))
    store.save(_tokens(access="second"))

    stored = store.get()

    assert stored is not None
    assert stored.access_token == "second"


def test_clear_removes_tokens(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.duckdb")
    store.save(_tokens())

    store.clear()

    assert store.get() is None


def test_persists_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "tokens.duckdb"
    TokenStore(db_path).save(_tokens(access="persisted"))

    stored = TokenStore(db_path).get()

    assert stored is not None
    assert stored.access_token == "persisted"


def test_is_valid_respects_margin() -> None:
    soon = OAuthTokens(
        access_token="a",
        expires_at=datetime.now(UTC) + timedelta(seconds=100),
    )

    assert not soon.is_valid(margin_seconds=300)
    assert soon.is_valid(margin_seconds=10)


def test_is_expired() -> None:
    expired = OAuthTokens(
        access_token="a",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert expired.is_expired
