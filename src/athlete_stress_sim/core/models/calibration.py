"""Calibration of the Banister parameters from observed performance (``RF-03.2``).

The extended Kalman filter tunes ``k1``, ``k2``, ``tau1`` and ``tau2`` from the
observed running performance (efficiency factor, see
:mod:`athlete_stress_sim.core.metrics.performance`). Observations are normalised
by their median so the fit is scale-free, and the filter is iterated over the
whole history so the static parameters converge on short series.

The fitted gains are rescaled to the prior's freshness amplitude before being
applied: the dashboard expresses freshness (TSB) in load units (``RF-05.1``), so
raw gains fitted to a dimensionless index would otherwise collapse the readiness
signal. When the fit does not explain enough variance (or there is too little
data) the prior is returned unchanged, which is the expected behaviour while the
history is still short.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field

from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response
from athlete_stress_sim.core.models.ekf import BanisterEKF

MIN_OBSERVATIONS = 4
"""Minimum number of observed performances required to attempt a fit."""

MIN_R_SQUARED = 0.1
"""Minimum coefficient of determination for accepting calibrated parameters."""

CALIBRATION_EPOCHS = 60
"""Passes over the history used to converge the static EKF parameters."""

_PROCESS_NOISE = (1.0, 1.0, 1e-2, 1e-2, 1e-2, 1e-2)
_MIN_SCALE = 1e-9


class CalibrationResult(BaseModel):
    """Outcome of fitting the Banister parameters to observed performance."""

    params: BanisterParams = Field(description="Effective parameters (calibrated or prior).")
    priors: BanisterParams = Field(description="Reference priors used as the fallback.")
    calibrated: bool = Field(description="Whether the fit passed the quality gate.")
    observations: int = Field(ge=0, description="Number of observed performance points.")
    r_squared: float | None = Field(
        default=None, description="Coefficient of determination of the fit, if computable."
    )
    baseline_efficiency: float | None = Field(
        default=None, description="Median efficiency factor used to normalise observations."
    )


def calibrate_banister(
    daily_loads: Sequence[float],
    observations: Mapping[int, float],
    prior: BanisterParams,
    *,
    epochs: int = CALIBRATION_EPOCHS,
) -> CalibrationResult:
    """Fit the Banister parameters with the EKF, falling back to the prior.

    Observations are raw efficiency factors keyed by day index. They are
    normalised by their median so the fit is scale-free, then the EKF is iterated
    so the static parameters converge. The fit is accepted only when it has enough
    observations and explains a minimum share of the variance; otherwise the prior
    is returned unchanged.

    Args:
        daily_loads: One training-load value per day (rest days = ``0.0``).
        observations: Observed efficiency factors keyed by day index.
        prior: Reference parameters used as the EKF prior and as the fallback.
        epochs: Number of passes over the history used to converge the filter.

    Returns:
        The calibration outcome, always carrying usable effective parameters.
    """
    count = len(observations)
    if count < MIN_OBSERVATIONS or not daily_loads:
        return CalibrationResult(params=prior, priors=prior, calibrated=False, observations=count)

    baseline = statistics.median(observations.values())
    if not math.isfinite(baseline) or baseline <= 0.0:
        return CalibrationResult(params=prior, priors=prior, calibrated=False, observations=count)

    relative = {day: value / baseline for day, value in observations.items()}
    measurement_noise = statistics.pvariance(relative.values())
    if not math.isfinite(measurement_noise) or measurement_noise <= 0.0:
        return CalibrationResult(
            params=prior,
            priors=prior,
            calibrated=False,
            observations=count,
            baseline_efficiency=baseline,
        )

    relative_prior = prior.model_copy(update={"p0": 1.0})
    ekf = BanisterEKF(
        relative_prior,
        process_noise=_PROCESS_NOISE,
        measurement_noise=measurement_noise,
    )
    for _ in range(epochs):
        ekf.run(daily_loads, relative)

    fit = ekf.parameters
    r_squared = _r_squared(daily_loads, fit, relative)
    calibrated = (
        r_squared is not None
        and math.isfinite(r_squared)
        and r_squared >= MIN_R_SQUARED
        and fit.tau1 > fit.tau2
    )
    params = _rescale_to_prior(fit, prior, daily_loads) if calibrated else prior
    return CalibrationResult(
        params=params,
        priors=prior,
        calibrated=calibrated,
        observations=count,
        r_squared=r_squared,
        baseline_efficiency=baseline,
    )


def _r_squared(
    daily_loads: Sequence[float],
    params: BanisterParams,
    observations: Mapping[int, float],
) -> float | None:
    """Return the coefficient of determination of a fit, or ``None``."""
    valid_days = [day for day in sorted(observations) if 0 <= day < len(daily_loads)]
    if not valid_days:
        return None
    fitted = impulse_response(daily_loads, params)
    measured = [observations[day] for day in valid_days]
    predicted = [fitted.performance[day] for day in valid_days]
    mean = statistics.fmean(measured)
    ss_res = sum((actual - model) ** 2 for actual, model in zip(measured, predicted, strict=True))
    ss_tot = sum((actual - mean) ** 2 for actual in measured)
    if ss_tot <= 0.0:
        return None
    return 1.0 - ss_res / ss_tot


def _rescale_to_prior(
    fit: BanisterParams,
    prior: BanisterParams,
    daily_loads: Sequence[float],
) -> BanisterParams:
    """Rescale the fitted gains to the prior's freshness amplitude."""
    fit_std = statistics.pstdev(_net_series(daily_loads, fit))
    prior_std = statistics.pstdev(_net_series(daily_loads, prior))
    if fit_std <= _MIN_SCALE or prior_std <= _MIN_SCALE:
        return prior
    scale = prior_std / fit_std
    return BanisterParams(
        p0=prior.p0,
        k1=fit.k1 * scale,
        k2=fit.k2 * scale,
        tau1=fit.tau1,
        tau2=fit.tau2,
    )


def _net_series(daily_loads: Sequence[float], params: BanisterParams) -> list[float]:
    """Return the ``k1*g - k2*h`` series for the given parameters."""
    return impulse_response(daily_loads, params).freshness
