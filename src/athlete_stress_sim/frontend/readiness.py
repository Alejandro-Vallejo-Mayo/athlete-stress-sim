"""Daily readiness heuristic derived from the Banister freshness (``RF-05.1``).

Freshness (``fitness - fatigue``) is positive when the athlete is recovered and
negative when fatigue dominates. It is mapped to a traffic light: ``READY`` when
non-negative, ``REST`` below :data:`CAUTION_FLOOR`, and ``CAUTION`` in between.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CAUTION_FLOOR = -5.0
"""Freshness (arbitrary units) below which the athlete should rest."""


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


READINESS_META: dict[Readiness, ReadinessMeta] = {
    Readiness.READY: ReadinessMeta(
        label="Ready",
        color="green",
        description="Freshness is positive; ready for a quality session.",
    ),
    Readiness.CAUTION: ReadinessMeta(
        label="Caution",
        color="yellow",
        description="Mild accumulated fatigue; keep the intensity in check.",
    ),
    Readiness.REST: ReadinessMeta(
        label="Rest",
        color="red",
        description="High accumulated fatigue; prioritise recovery.",
    ),
}


def readiness_level(freshness: float) -> Readiness:
    """Classify the daily freshness into a readiness level.

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
