"""Daily readiness derived from the Banister freshness (``RF-05.1``).

The absolute freshness value depends on the arbitrary scale of the model gains
and on the chosen priors. To keep the traffic light meaningful when the
calibration falls back to priors, readiness is ranked against the athlete's own
recent freshness history (last :data:`READINESS_WINDOW_DAYS` days). With too
little history it falls back to the absolute break-even thresholds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from athlete_stress_sim.frontend.theme import COLORS

CAUTION_FLOOR = -5.0
"""Absolute freshness threshold used when there is not enough history (AU)."""

READINESS_WINDOW_DAYS = 90
"""Rolling window (days) used as the athlete's reference distribution."""

MIN_HISTORY_DAYS = 14
"""Minimum history length required to use the relative readiness ranking."""

READY_PERCENTILE = 0.5
"""At or above this freshness percentile the athlete is ready."""

CAUTION_PERCENTILE = 0.15
"""Below this percentile the athlete should rest."""


class Readiness(StrEnum):
    """Daily readiness level shown as a traffic light."""

    READY = "ready"
    CAUTION = "caution"
    REST = "rest"


@dataclass(frozen=True)
class ReadinessMeta:
    """Presentation metadata for a readiness level."""

    label: str
    color: str
    description: str
    action: str


READINESS_META: dict[Readiness, ReadinessMeta] = {
    Readiness.READY: ReadinessMeta(
        label="Ready",
        color=COLORS["ready"],
        description="Freshness is at or above your recent median; good for quality work.",
        action="Good day for quality work. Keep the session controlled.",
    ),
    Readiness.CAUTION: ReadinessMeta(
        label="Caution",
        color=COLORS["caution"],
        description="Freshness is below your recent median; keep the intensity in check.",
        action="Keep intensity in check and avoid adding load today.",
    ),
    Readiness.REST: ReadinessMeta(
        label="Rest",
        color=COLORS["rest"],
        description="Freshness is in the lowest part of your recent range; prioritise recovery.",
        action="Prioritise recovery: easy movement or rest today.",
    ),
}


def assess_readiness(
    freshness: float,
    history: Sequence[float],
) -> tuple[Readiness, float | None]:
    """Classify freshness relative to the athlete's recent history.

    Args:
        freshness: Current ``fitness - fatigue`` in arbitrary units.
        history: Freshness values for the available daily history.

    Returns:
        The readiness level and the current freshness percentile, or ``None``
        when the history is too short and the absolute thresholds are used.
    """
    window = list(history[-READINESS_WINDOW_DAYS:])
    if len(window) < MIN_HISTORY_DAYS:
        return readiness_level(freshness), None
    percentile = freshness_percentile(freshness, window)
    if percentile >= READY_PERCENTILE:
        return Readiness.READY, percentile
    if percentile >= CAUTION_PERCENTILE:
        return Readiness.CAUTION, percentile
    return Readiness.REST, percentile


def freshness_percentile(freshness: float, history: Sequence[float]) -> float:
    """Return the fraction of historical values at or below ``freshness``."""
    if not history:
        return 1.0
    return sum(1 for value in history if value <= freshness) / len(history)


def readiness_level(freshness: float) -> Readiness:
    """Classify freshness with absolute thresholds (fallback for short history).

    Args:
        freshness: ``fitness - fatigue`` in arbitrary units.

    Returns:
        ``READY`` when freshness is non-negative, ``REST`` below
        :data:`CAUTION_FLOOR`, and ``CAUTION`` in between.
    """
    if freshness >= 0.0:
        return Readiness.READY
    if freshness >= CAUTION_FLOOR:
        return Readiness.CAUTION
    return Readiness.REST
