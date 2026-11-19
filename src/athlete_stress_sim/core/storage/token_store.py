"""DuckDB-backed persistence for Polar OAuth2 tokens.

The token set is stored locally (``RNF-01``) in the analytical database used by
the rest of the project. Secrets are kept in plaintext for now; at-rest
encryption is deferred to the security review in S16.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
from pydantic import BaseModel

_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_tokens (
    user_id VARCHAR,
    access_token VARCHAR NOT NULL,
    refresh_token VARCHAR NOT NULL,
    token_type VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    expires_at_epoch BIGINT NOT NULL,
    updated_at_epoch BIGINT NOT NULL
)
"""


class OAuthTokens(BaseModel):
    """OAuth2 token set issued by Polar for a single user."""

    access_token: str
    expires_at: datetime
    refresh_token: str = ""
    token_type: str = "Bearer"
    scope: str = ""
    user_id: str = ""

    @property
    def is_expired(self) -> bool:
        """Whether the access token is past its expiry instant."""
        return datetime.now(UTC) >= self.expires_at

    def is_valid(self, margin_seconds: int = 300) -> bool:
        """Whether the access token is usable for at least ``margin_seconds``."""
        return datetime.now(UTC) + timedelta(seconds=margin_seconds) < self.expires_at


class TokenStore:
    """Persist the active OAuth2 token set in a local DuckDB database.

    Args:
        db_path: Path to the DuckDB file. Parent directories are created if needed.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(_SCHEMA)
        finally:
            connection.close()

    def save(self, tokens: OAuthTokens) -> None:
        """Store ``tokens`` as the active token set, replacing any previous one."""
        connection = self._connect()
        try:
            connection.execute("DELETE FROM oauth_tokens WHERE user_id = ?", [tokens.user_id])
            connection.execute(
                "INSERT INTO oauth_tokens VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    tokens.user_id,
                    tokens.access_token,
                    tokens.refresh_token,
                    tokens.token_type,
                    tokens.scope,
                    int(tokens.expires_at.timestamp()),
                    int(datetime.now(UTC).timestamp()),
                ],
            )
        finally:
            connection.close()

    def get(self) -> OAuthTokens | None:
        """Return the most recently stored token set, or ``None`` if empty."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT user_id, access_token, refresh_token, token_type, scope, expires_at_epoch "
                "FROM oauth_tokens ORDER BY updated_at_epoch DESC LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        user_id, access_token, refresh_token, token_type, scope, expires_at_epoch = row
        return OAuthTokens(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            scope=scope,
            expires_at=datetime.fromtimestamp(int(expires_at_epoch), UTC),
        )

    def clear(self) -> None:
        """Remove every stored token set."""
        connection = self._connect()
        try:
            connection.execute("DELETE FROM oauth_tokens")
        finally:
            connection.close()
