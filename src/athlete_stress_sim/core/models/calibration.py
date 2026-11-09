"""Calibration of the Banister gains with fixed time constants (``RF-03.2``).

The fitness-fatigue model is ill-conditioned when ``k1/k2`` and ``tau1/tau2`` are
estimated jointly from a single noisy performance series. Following the
literature (Vermeire et al., 2022; Marchal et al., 2025), this module keeps the
time constants fixed at the physiological priors and estimates only the baseline
and the two gains with a bounded, ridge-regularised linear least-squares fit.

Observations are the session efficiency factor (``speed / HR``), normalised by
their median so the fit is scale-free. The fitted gains are then rescaled to the
prior's freshness amplitude so the dashboard keeps expressing freshness (TSB) in
load units (``RF-05.1``). A model is accepted only when it explains enough
in-sample variance *and* beats the prior-shaped baseline in leave-one-out
cross-validation; otherwise the prior is returned unchanged.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import lsq_linear

from athlete_stress_sim.core.models.banister import BanisterParams, impulse_response

MIN_OBSERVATIONS = 8
"""Minimum number of observed performances required to attempt a fit."""

MIN_R_SQUARED = 0.1
"""Minimum in-sample coefficient of determination for accepting the fit."""

MIN_CV_IMPROVEMENT = 0.05
"""Minimum relative RMSE improvement over the prior baseline in cross-validation."""

RIDGE_LAMBDA = 1e-2
"""Ridge strength pulling the fitted coefficients toward the prior shape."""

_MIN_SCALE = 1e-9
_PARAMETER_COUNT = 3
_SQRT_RIDGE = math.sqrt(RIDGE_LAMBDA)


class CalibrationResult(BaseModel):
    """Outcome of fitting the Banister gains to observed performance."""

    params: BanisterParams = Field(description="Effective parameters (calibrated or prior).")
    priors: BanisterParams = Field(description="Reference priors used as the fallback.")
    calibrated: bool = Field(description="Whether the fit passed the quality gate.")
    observations: int = Field(ge=0, description="Number of observed performance points.")
    r_squared: float | None = Field(
        default=None, description="In-sample coefficient of determination of the fit."
    )
    baseline_efficiency: float | None = Field(
        default=None, description="Median efficiency factor used to normalise observations."
    )
    cv_rmse: float | None = Field(
        default=None, description="Leave-one-out RMSE of the calibrated model."
    )
    prior_cv_rmse: float | None = Field(
        default=None, description="Leave-one-out RMSE of the prior-shaped baseline."
    )
    cv_improvement: float | None = Field(
        default=None, description="Relative RMSE improvement over the prior baseline."
    )


def calibrate_banister(  # noqa: PLR0911
    daily_loads: Sequence[float],
    observations: Mapping[int, float],
    prior: BanisterParams,
) -> CalibrationResult:
    """Fit the Banister gains with the time constants fixed at the prior.

    Args:
        daily_loads: One training-load value per day (rest days = ``0.0``).
        observations: Observed efficiency factors keyed by day index.
        prior: Reference parameters; its time constants stay fixed and it is the
            fallback when the fit does not pass the quality gate.

    Returns:
        The calibration outcome, always carrying usable effective parameters.
    """
    count = len(observations)
    if count < MIN_OBSERVATIONS or not daily_loads:
        return _fallback(prior, count)

    baseline = statistics.median(observations.values())
    if not math.isfinite(baseline) or baseline <= 0.0:
        return _fallback(prior, count)

    relative = {day: value / baseline for day, value in observations.items()}
    days = sorted(day for day in relative if 0 <= day < len(daily_loads))
    if len(days) < MIN_OBSERVATIONS:
        return _fallback(prior, count, baseline=baseline)
    y = np.array([relative[day] for day in days], dtype=float)
    if float(np.std(y)) <= _MIN_SCALE:
        return _fallback(prior, count, baseline=baseline)

    response = impulse_response(daily_loads, prior)
    fitness = np.asarray(response.fitness, dtype=float)
    fatigue = np.asarray(response.fatigue, dtype=float)
    net_prior = prior.k1 * fitness - prior.k2 * fatigue
    offset = float(np.median(net_prior))
    spread = float(np.std(net_prior))
    if spread <= _MIN_SCALE:
        return _fallback(prior, count, baseline=baseline)

    design = np.column_stack([np.ones(len(daily_loads), dtype=float), fitness, -fatigue])
    rows = design[days]
    scales = _column_scales(rows)
    prior_coefficients = _prior_coefficients(y, offset, spread, prior)
    coefficients = _solve_ridge(rows, y, prior_coefficients, scales)
    if coefficients is None:
        return _fallback(prior, count, baseline=baseline)

    r_squared = _r_squared(y, rows @ coefficients)
    cross_validation = _cross_validate(
        rows, y, offset=offset, spread=spread, prior=prior, scales=scales
    )
    if cross_validation is None:
        return _fallback(prior, count, baseline=baseline, r_squared=r_squared)
    cv_rmse, prior_cv_rmse = cross_validation
    improvement = 1.0 - cv_rmse / prior_cv_rmse if prior_cv_rmse > _MIN_SCALE else -math.inf

    p0, k1, k2 = (float(value) for value in coefficients)
    if k1 <= 0.0 or k2 <= 0.0:
        return _fallback(
            prior,
            count,
            baseline=baseline,
            r_squared=r_squared,
            cv_rmse=cv_rmse,
            prior_cv_rmse=prior_cv_rmse,
            cv_improvement=improvement,
        )
    fit = BanisterParams(p0=p0, k1=k1, k2=k2, tau1=prior.tau1, tau2=prior.tau2)
    calibrated = (
        r_squared is not None
        and math.isfinite(r_squared)
        and r_squared >= MIN_R_SQUARED
        and math.isfinite(improvement)
        and improvement >= MIN_CV_IMPROVEMENT
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
        cv_rmse=cv_rmse,
        prior_cv_rmse=prior_cv_rmse,
        cv_improvement=improvement,
    )


def _fallback(
    prior: BanisterParams,
    observations: int,
    *,
    baseline: float | None = None,
    r_squared: float | None = None,
    cv_rmse: float | None = None,
    prior_cv_rmse: float | None = None,
    cv_improvement: float | None = None,
) -> CalibrationResult:
    """Return the prior unchanged with whatever diagnostics were computed."""
    return CalibrationResult(
        params=prior,
        priors=prior,
        calibrated=False,
        observations=observations,
        r_squared=r_squared,
        baseline_efficiency=baseline,
        cv_rmse=cv_rmse,
        prior_cv_rmse=prior_cv_rmse,
        cv_improvement=cv_improvement,
    )


def _column_scales(rows: np.ndarray) -> np.ndarray:
    """Return per-column scales used to stabilise the ridge system."""
    return np.array(
        [
            1.0,
            max(float(np.std(rows[:, 1])), _MIN_SCALE),
            max(float(np.std(rows[:, 2])), _MIN_SCALE),
        ]
    )


def _prior_coefficients(
    observations: np.ndarray,
    offset: float,
    spread: float,
    prior: BanisterParams,
) -> np.ndarray:
    """Return the prior shape with its intercept and scale matched to the data."""
    observed_spread = float(np.std(observations))
    scale = observed_spread / spread if spread > _MIN_SCALE else 0.0
    return np.array([1.0 - scale * offset, scale * prior.k1, scale * prior.k2], dtype=float)


def _solve_ridge(
    rows: np.ndarray,
    observations: np.ndarray,
    prior_coefficients: np.ndarray,
    scales: np.ndarray,
) -> np.ndarray | None:
    """Solve the bounded ridge least-squares problem in standardised units."""
    if len(observations) < _PARAMETER_COUNT:
        return None
    standardised = rows / scales
    prior_standardised = prior_coefficients * scales
    design = np.vstack([standardised, _SQRT_RIDGE * np.eye(_PARAMETER_COUNT, dtype=float)])
    target = np.concatenate([observations, _SQRT_RIDGE * prior_standardised])
    lower = np.array([-10.0, 0.0, 0.0], dtype=float) * scales
    upper = np.array([10.0, np.inf, np.inf], dtype=float) * scales
    solution = lsq_linear(design, target, bounds=(lower, upper), method="trf")
    if not solution.success:
        return None
    coefficients: np.ndarray = np.asarray(solution.x, dtype=float) / scales
    if not np.all(np.isfinite(coefficients)):
        return None
    return coefficients


def _cross_validate(
    rows: np.ndarray,
    observations: np.ndarray,
    *,
    offset: float,
    spread: float,
    prior: BanisterParams,
    scales: np.ndarray,
) -> tuple[float, float] | None:
    """Return the leave-one-out RMSE of the fit and of the prior baseline."""
    count = len(observations)
    if count < _PARAMETER_COUNT + 1:
        return None
    squared_fit: list[float] = []
    squared_prior: list[float] = []
    for index in range(count):
        train = np.ones(count, dtype=bool)
        train[index] = False
        prior_coefficients = _prior_coefficients(observations[train], offset, spread, prior)
        coefficients = _solve_ridge(rows[train], observations[train], prior_coefficients, scales)
        if coefficients is None:
            return None
        predicted_fit = float(rows[index] @ coefficients)
        predicted_prior = float(rows[index] @ prior_coefficients)
        squared_fit.append((predicted_fit - observations[index]) ** 2)
        squared_prior.append((predicted_prior - observations[index]) ** 2)
    return (
        math.sqrt(float(np.mean(squared_fit))),
        math.sqrt(float(np.mean(squared_prior))),
    )


def _r_squared(measured: np.ndarray, predicted: np.ndarray) -> float | None:
    """Return the coefficient of determination, or ``None`` when undefined."""
    mean = float(np.mean(measured))
    ss_res = float(np.sum((measured - predicted) ** 2))
    ss_tot = float(np.sum((measured - mean) ** 2))
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
