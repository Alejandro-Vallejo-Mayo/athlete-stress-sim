"""Central configuration: physiological constants and Polar credentials.

Credentials are read from environment variables / a ``.env`` file (see
``.env.example``). Physiological values belong to the *user zero* and act as
*priors* until the EKF tunes them (S9).
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    b: float = Field(default=1.92, description="TRIMP exponential coefficient (1.92 for men).")
    rpe_alpha: float = Field(default=1.0, gt=0, description="RPE factor exponent (gym).")


class PolarConfig(BaseSettings):
    """Polar AccessLink OAuth2 credentials (placeholders until S2)."""

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
    access_token: str = Field(default="", description="Current OAuth2 access token.")
    refresh_token: str = Field(default="", description="OAuth2 refresh token.")


physiology = PhysiologicalConfig()
polar = PolarConfig()
