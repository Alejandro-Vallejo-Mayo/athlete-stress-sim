"""Session-RPE load for strength/gym sessions (Foster et al., 2001).

Strength training is quantified with the session rating of perceived exertion
(sRPE) method: the CR-10 rating (0-10) multiplied by the session duration in
minutes. This yields an internal-load value in arbitrary units that can be
combined with running TRIMP into a single load series.
"""

from __future__ import annotations

_SECONDS_PER_MINUTE = 60.0
MIN_RPE = 0.0
MAX_RPE = 10.0


def session_rpe_load(rpe: float, duration_s: float) -> float:
    """Compute Foster's session-RPE load for a strength session.

    Args:
        rpe: Session rating of perceived exertion on the Borg CR-10 scale (0-10).
        duration_s: Session duration in seconds (typically from the FIT file).

    Returns:
        The session load in arbitrary units (``rpe * duration_min``).

    Raises:
        ValueError: If ``rpe`` is outside ``[0, 10]`` or ``duration_s`` is negative.
    """
    if not MIN_RPE <= rpe <= MAX_RPE:
        raise ValueError(f"rpe must be between {MIN_RPE} and {MAX_RPE}")
    if duration_s < 0:
        raise ValueError("duration_s must not be negative")
    return rpe * (duration_s / _SECONDS_PER_MINUTE)
