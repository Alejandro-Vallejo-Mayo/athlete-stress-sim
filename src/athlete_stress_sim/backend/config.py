"""Central configuration: physiological constants, Polar OAuth2 and storage.

Credentials are read from environment variables / a ``.env`` file (see
``.env.example``). Physiological values belong to the *user zero* and act as
*priors* until the EKF tunes them (S9).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from athlete_stress_sim.core.metrics.trimp import Sex


class PhysiologicalConfig(BaseSettings):
    """Physiological constants and reference parameters of the Banister model."""

    model_config = SettingsConfigDict(
        env_prefix="ATHLETE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hr_max: int = Field(default=200, gt=0, description="Maximum heart rate (bpm).")
    hr_rest: int = Field(default=55, gt=0, description="Resting heart rate (bpm).")

    tau_1: float = Field(default=45.0, gt=0, description="Fitness time constant (days).")
    tau_2: float = Field(default=15.0, gt=0, description="Fatigue time constant (days).")

    k_1: float = Field(default=1.0, description="Fitness gain.")
    k_2: float = Field(default=2.0, description="Fatigue gain.")

    sex: Sex = Field(default=Sex.MALE, description="Selects the Banister TRIMP coefficients.")


class PolarConfig(BaseSettings):
    """Polar AccessLink OAuth2 settings and endpoint URLs."""

    model_config = SettingsConfigDict(
        env_prefix="POLAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    client_id: str = Field(default="", description="Polar AccessLink app client ID.")
    client_secret: str = Field(default="", description="Polar AccessLink client secret.")
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="Redirect URI registered in Polar.",
    )
    authorize_url: str = Field(
        default="https://flow.polar.com/oauth2/authorization",
        description="Polar OAuth2 authorization endpoint.",
    )
    token_url: str = Field(
        default="https://polarremote.com/v2/oauth2/token",
        description="Polar OAuth2 token endpoint.",
    )
    api_url: str = Field(
        default="https://www.polaraccesslink.com/v3",
        description="Polar AccessLink REST API base URL.",
    )
    scope: str = Field(default="accesslink.read_all", description="Requested OAuth2 scope.")
    member_id: str = Field(
        default="athlete-stress-sim",
        description="Partner member id used to register the Polar user.",
    )
    sync_on_startup: bool = Field(
        default=True,
        description="Run a catch-up sync in the background when the backend starts.",
    )


class StorageConfig(BaseSettings):
    """Local persistence settings."""

    model_config = SettingsConfigDict(
        env_prefix="ATHLETE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(
        default=Path("data/athleta.duckdb"),
        description="Path to the local DuckDB analytical database.",
    )
    raw_data_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory where raw Polar files (FIT/TCX) are stored.",
    )


physiology = PhysiologicalConfig()
polar = PolarConfig()
storage = StorageConfig()
