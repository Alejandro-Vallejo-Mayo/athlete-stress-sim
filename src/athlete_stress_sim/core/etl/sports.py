"""Classification of Polar/FIT sports relevant to the load model.

The project treats running and strength training differently (Banister TRIMP vs
session-RPE). This module maps the raw FIT ``sport``/``sub_sport`` strings to a
strength-training check.
"""

from __future__ import annotations

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


def is_strength(sport: str, sub_sport: str = "") -> bool:
    """Whether a session is a strength/gym session.

    Args:
        sport: FIT ``sport`` value (e.g. ``"training"``).
        sub_sport: FIT ``sub_sport`` value (e.g. ``"strength_training"``).

    Returns:
        ``True`` if either field matches a known strength-training value.
    """
    return _normalize(sport) in _STRENGTH_SPORTS or _normalize(sub_sport) in _STRENGTH_SUB_SPORTS


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")
