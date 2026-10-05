"""Acute:Chronic Workload Ratio (ACWR) using exponentially weighted moving averages.

Implements the EWMA model of Williams et al. (2017) and Murray et al. (2017):
``EWMA_today = lambda * load_today + (1 - lambda) * EWMA_yesterday`` with
``lambda = 2 / (N + 1)``. The ratio of the acute (7-day) to the chronic (28-day)
EWMA estimates injury risk (Gabbett's sweet-spot model).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

DEFAULT_ACUTE_DAYS = 7
DEFAULT_CHRONIC_DAYS = 28

# Risk-zone boundaries (Gabbett; Williams et al. 2017).
_UNDERTRAINING_MAX = 0.8
_SWEET_SPOT_MAX = 1.3
_WARNING_MAX = 1.5


class RiskZone(StrEnum):
    """Injury-risk zone derived from the ACWR value."""

    UNDERTRAINING = "undertraining"
    SWEET_SPOT = "sweet_spot"
    WARNING = "warning"
    DANGER = "danger"


def ewma_lambda(days: int) -> float:
    """Return the EWMA decay factor ``2 / (N + 1)`` for an ``N``-day window.

    Args:
        days: Window length in days (e.g. 7 for acute, 28 for chronic).

    Raises:
        ValueError: If ``days`` is less than 1.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    return 2.0 / (days + 1.0)


def ewma_series(values: Sequence[float], lam: float) -> list[float]:
    """Compute the EWMA of a series, seeded with its first value.

    Args:
        values: Daily load values (rest days included as ``0.0``).
        lam: Decay factor in ``(0, 1]``.

    Returns:
        The EWMA evaluated at each day, same length as ``values``.

    Raises:
        ValueError: If ``lam`` is not in ``(0, 1]``.
    """
    if not 0.0 < lam <= 1.0:
        raise ValueError("lam must be in (0, 1]")
    if not values:
        return []
    result = [values[0]]
    for value in values[1:]:
        result.append(value * lam + result[-1] * (1.0 - lam))
    return result


def acwr_series(
    daily_loads: Sequence[float],
    acute_days: int = DEFAULT_ACUTE_DAYS,
    chronic_days: int = DEFAULT_CHRONIC_DAYS,
) -> list[float]:
    """Compute the per-day acute:chronic workload ratio.

    Days with a zero chronic EWMA yield ``0.0`` (no load history yet).
    """
    acute = ewma_series(daily_loads, ewma_lambda(acute_days))
    chronic = ewma_series(daily_loads, ewma_lambda(chronic_days))
    return [a / c if c > 0.0 else 0.0 for a, c in zip(acute, chronic, strict=True)]


def classify_risk(acwr: float) -> RiskZone:
    """Classify an ACWR value into its injury-risk zone."""
    if acwr < _UNDERTRAINING_MAX:
        return RiskZone.UNDERTRAINING
    if acwr <= _SWEET_SPOT_MAX:
        return RiskZone.SWEET_SPOT
    if acwr <= _WARNING_MAX:
        return RiskZone.WARNING
    return RiskZone.DANGER
