"""Banister fitness-fatigue impulse-response model (``RF-03.1``).

Two first-order responses (fitness ``g`` and fatigue ``h``) are driven by the
daily training load ``w(t)``::

    dg/dt = -g / tau1 + w(t)
    dh/dt = -h / tau2 + w(t)
    p(t)  = p0 + k1 * g(t) - k2 * h(t)

For daily (impulsive) loads the differential system has the exact recurrence
solution used by :func:`impulse_response`. :func:`solve_banister_ode` provides a
numerical cross-check with ``scipy.integrate.solve_ivp`` (``odeint`` is
deprecated).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, Field
from scipy.integrate import solve_ivp


class BanisterParams(BaseModel):
    """Parameters of the two-component Banister model.

    Typical values (Morton et al., 1990): ``k1=1``, ``k2=2``, ``tau1=45`` days
    (fitness) and ``tau2=15`` days (fatigue), with ``k2 > k1`` and ``tau1 > tau2``.
    """

    p0: float = Field(default=0.0, description="Baseline performance (arbitrary units).")
    k1: float = Field(default=1.0, gt=0, description="Fitness gain.")
    k2: float = Field(default=2.0, gt=0, description="Fatigue gain.")
    tau1: float = Field(default=45.0, gt=0, description="Fitness time constant (days).")
    tau2: float = Field(default=15.0, gt=0, description="Fatigue time constant (days).")


class BanisterResult(BaseModel):
    """Per-day evolution of the model state and its derived metrics."""

    fitness: list[float]
    fatigue: list[float]
    performance: list[float]
    freshness: list[float]


def impulse_response(
    daily_loads: Sequence[float],
    params: BanisterParams,
) -> BanisterResult:
    """Solve the Banister system exactly for daily (impulsive) loads.

    Args:
        daily_loads: One training-load value per day (rest days = ``0.0``).
        params: Model parameters.

    Returns:
        The per-day fitness, fatigue, performance and freshness series.
    """
    decay1 = math.exp(-1.0 / params.tau1)
    decay2 = math.exp(-1.0 / params.tau2)
    fitness: list[float] = []
    fatigue: list[float] = []
    performance: list[float] = []
    freshness: list[float] = []
    g = 0.0
    h = 0.0
    for load in daily_loads:
        g = g * decay1 + load
        h = h * decay2 + load
        net = params.k1 * g - params.k2 * h
        fitness.append(g)
        fatigue.append(h)
        freshness.append(net)
        performance.append(params.p0 + net)
    return BanisterResult(
        fitness=fitness,
        fatigue=fatigue,
        performance=performance,
        freshness=freshness,
    )


def solve_banister_ode(
    daily_loads: Sequence[float],
    params: BanisterParams,
    *,
    rtol: float = 1e-8,
    atol: float = 1e-8,
) -> BanisterResult:
    """Numerically integrate the Banister ODEs (piecewise-constant load).

    The daily load is held constant over each day; ``solve_ivp`` (RK45) returns
    the state at the end of every day. This is the continuous-input
    interpretation used as a numerical cross-check against the exact recurrence.

    Args:
        daily_loads: One training-load value per day (rest days = ``0.0``).
        params: Model parameters.
        rtol: Relative tolerance passed to ``solve_ivp``.
        atol: Absolute tolerance passed to ``solve_ivp``.

    Returns:
        The per-day fitness, fatigue, performance and freshness series.
    """
    loads = list(daily_loads)
    n = len(loads)
    if n == 0:
        return BanisterResult(fitness=[], fatigue=[], performance=[], freshness=[])

    def load_at(time: float) -> float:
        return loads[min(int(time), n - 1)]

    def rhs(time: float, state: list[float]) -> list[float]:
        g, h = state
        load = load_at(time)
        return [-g / params.tau1 + load, -h / params.tau2 + load]

    solution = solve_ivp(
        rhs,
        (0.0, float(n)),
        [0.0, 0.0],
        t_eval=list(range(1, n + 1)),
        rtol=rtol,
        atol=atol,
        max_step=1.0,
    )
    fitness = [float(value) for value in solution.y[0]]
    fatigue = [float(value) for value in solution.y[1]]
    performance: list[float] = []
    freshness: list[float] = []
    for g, h in zip(fitness, fatigue, strict=True):
        net = params.k1 * g - params.k2 * h
        freshness.append(net)
        performance.append(params.p0 + net)
    return BanisterResult(
        fitness=fitness,
        fatigue=fatigue,
        performance=performance,
        freshness=freshness,
    )
