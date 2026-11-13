"""Classification of Polar/FIT sports relevant to the load model.

The project treats running, elliptical and strength training differently: running
and elliptical contribute a Banister TRIMP computed from heart rate, while strength
sessions use session-RPE. This module maps the raw FIT ``sport``/``sub_sport``
strings to a :class:`SportKind` so every consumer applies the same rules.
"""

from __future__ import annotations

from enum import StrEnum

_RUNNING_SPORTS = {"running", "run"}
_RUNNING_SUB_SPORTS = {"street", "trail", "track", "treadmill", "road"}
# Generic FIT sports whose family is only known from the sub-sport.
_AMBIGUOUS_SPORTS = {"", "generic", "other", "fitness_equipment"}

# Values provisionally mapped from the FIT profile; verified against a real
# Polar Ignite strength session once available.
_STRENGTH_SPORTS = {"training", "strength_training", "strength", "weight_training"}
_STRENGTH_SUB_SPORTS = {
    "strength_training",
    "muscle_toning",
    "core_training",
    "strength",
    "weight_training",
}

# Polar usually reports ``sub_sport="elliptical"`` under a generic sport, but the
# sport itself may carry the elliptical label depending on the device. Real
# Polar Ignite elliptical sessions arrive as ``training``/``cardio_training``.
_ELLIPTICAL_SPORTS = {"elliptical", "elliptical_trainer", "cross_trainer", "crosstrainer"}
_ELLIPTICAL_SUB_SPORTS = {
    "elliptical",
    "elliptical_trainer",
    "indoor_elliptical",
    "cross_trainer",
    "crosstrainer",
    "cardio_training",
}


class SportKind(StrEnum):
    """High-level activity family used by the load and running-only metrics."""

    RUNNING = "running"
    STRENGTH = "strength"
    ELLIPTICAL = "elliptical"
    OTHER = "other"


def classify_sport(sport: str, sub_sport: str = "") -> SportKind:
    """Classify a FIT sport/sub-sport pair into a :class:`SportKind`.

    Elliptical is checked before strength because Polar may report a generic
    ``sport="training"`` with ``sub_sport="elliptical"``, which must not be
    mistaken for a gym session.

    Args:
        sport: FIT ``sport`` value (e.g. ``"running"``).
        sub_sport: FIT ``sub_sport`` value (e.g. ``"street"``).

    Returns:
        The matching activity family, or :attr:`SportKind.OTHER` when unknown.
    """
    if is_elliptical(sport, sub_sport):
        return SportKind.ELLIPTICAL
    if is_strength(sport, sub_sport):
        return SportKind.STRENGTH
    if is_running(sport, sub_sport):
        return SportKind.RUNNING
    return SportKind.OTHER


def is_running(sport: str, sub_sport: str = "") -> bool:
    """Whether a session is a running activity.

    Args:
        sport: FIT ``sport`` value (e.g. ``"running"``).
        sub_sport: FIT ``sub_sport`` value (e.g. ``"street"``).

    Returns:
        ``True`` if the sport is running, or a generic sport with a running
        sub-sport such as ``street`` or ``treadmill``.
    """
    normalized_sport = _normalize(sport)
    if normalized_sport in _RUNNING_SPORTS:
        return True
    return normalized_sport in _AMBIGUOUS_SPORTS and _normalize(sub_sport) in _RUNNING_SUB_SPORTS


def is_strength(sport: str, sub_sport: str = "") -> bool:
    """Whether a session is a strength/gym session.

    Args:
        sport: FIT ``sport`` value (e.g. ``"training"``).
        sub_sport: FIT ``sub_sport`` value (e.g. ``"strength_training"``).

    Returns:
        ``True`` if either field matches a known strength-training value. A
        session already identified as elliptical is never treated as strength,
        even when Polar labels its sport as generic ``training``.
    """
    if is_elliptical(sport, sub_sport):
        return False
    return _normalize(sport) in _STRENGTH_SPORTS or _normalize(sub_sport) in _STRENGTH_SUB_SPORTS


def is_elliptical(sport: str, sub_sport: str = "") -> bool:
    """Whether a session is an elliptical/cross-trainer activity.

    Args:
        sport: FIT ``sport`` value (e.g. ``"fitness_equipment"``).
        sub_sport: FIT ``sub_sport`` value (e.g. ``"elliptical"``).

    Returns:
        ``True`` if either field matches a known elliptical value.
    """
    return (
        _normalize(sport) in _ELLIPTICAL_SPORTS or _normalize(sub_sport) in _ELLIPTICAL_SUB_SPORTS
    )


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")
