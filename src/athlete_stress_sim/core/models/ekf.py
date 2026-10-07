"""Extended Kalman filter for individual Banister parameters (``RF-03.2``).

Estimates the fitness gain ``k1``, fatigue gain ``k2`` and the time constants
``tau1``/``tau2`` online from observed performance. The state is augmented with
the four parameters (modeled as slow random walks)::

    state = [fitness, fatigue, k1, k2, tau1, tau2]

The time update is the nonlinear Banister recurrence; the measurement
``p = p0 + k1*fitness - k2*fatigue`` is applied through ``filterpy``'s
``ExtendedKalmanFilter.update`` (which takes the measurement Jacobian and
function as callables).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
from filterpy.kalman import ExtendedKalmanFilter

from athlete_stress_sim.core.models.banister import BanisterParams

_STATE_SIZE = 6
_MEASUREMENT_SIZE = 1

# Indexes into the state vector.
_G, _H, _K1, _K2, _TAU1, _TAU2 = range(_STATE_SIZE)

_MIN_GAIN = 1e-6
_MIN_TAU_DAYS = 1.0

DEFAULT_PROCESS_NOISE = (1.0, 1.0, 1e-3, 1e-3, 5e-3, 5e-3)
DEFAULT_INITIAL_COVARIANCE = (1.0, 1.0, 0.25, 0.25, 25.0, 25.0)
DEFAULT_MEASUREMENT_NOISE = 1.0


class BanisterEKF:
    """Augmented-state EKF estimating the four Banister parameters.

    Args:
        params: Prior parameters (used as the initial state for k1, k2, tau1, tau2).
        process_noise: Diagonal of the process-noise covariance ``Q``.
        initial_covariance: Diagonal of the initial state covariance ``P0``.
        measurement_noise: Scalar measurement-noise variance ``R``.
    """

    def __init__(
        self,
        params: BanisterParams,
        *,
        process_noise: Sequence[float] = DEFAULT_PROCESS_NOISE,
        initial_covariance: Sequence[float] = DEFAULT_INITIAL_COVARIANCE,
        measurement_noise: float = DEFAULT_MEASUREMENT_NOISE,
    ) -> None:
        self._p0 = params.p0
        self._filter = ExtendedKalmanFilter(dim_x=_STATE_SIZE, dim_z=_MEASUREMENT_SIZE)
        self._filter.x = np.array(
            [0.0, 0.0, params.k1, params.k2, params.tau1, params.tau2], dtype=float
        )
        self._filter.P = np.diag(np.asarray(initial_covariance, dtype=float))
        self._filter.Q = np.diag(np.asarray(process_noise, dtype=float))
        self._filter.R = np.array([[measurement_noise]], dtype=float)

    def predict(self, load: float) -> None:
        """Advance the model by one day with the given training ``load``."""
        jacobian = self._transition_jacobian(self._filter.x)
        self._filter.x = self._transition(self._filter.x, load)
        self._filter.F = jacobian
        self._filter.P = jacobian @ self._filter.P @ jacobian.T + self._filter.Q
        self._sanitize()

    def update(self, observation: float) -> None:
        """Correct the state with an observed performance value."""
        self._filter.update(
            observation,
            HJacobian=self._measurement_jacobian,
            Hx=self._measurement,
        )
        self._sanitize()

    def run(
        self,
        daily_loads: Sequence[float],
        observations: Mapping[int, float],
    ) -> None:
        """Run predict/update across a load series (``observations`` keyed by day)."""
        for day, load in enumerate(daily_loads):
            self.predict(load)
            if day in observations:
                self.update(observations[day])

    @property
    def state(self) -> tuple[float, float, float, float, float, float]:
        """The current ``(fitness, fatigue, k1, k2, tau1, tau2)`` state."""
        values = [float(value) for value in self._filter.x]
        return (values[0], values[1], values[2], values[3], values[4], values[5])

    @property
    def parameters(self) -> BanisterParams:
        """The current parameter estimates as a :class:`BanisterParams`."""
        state = self.state
        return BanisterParams(
            p0=self._p0,
            k1=state[_K1],
            k2=state[_K2],
            tau1=state[_TAU1],
            tau2=state[_TAU2],
        )

    @property
    def predicted_performance(self) -> float:
        """The performance predicted from the current state."""
        return float(self._measurement(self._filter.x))

    def _sanitize(self) -> None:
        state = self._filter.x
        state[_G] = max(state[_G], 0.0)
        state[_H] = max(state[_H], 0.0)
        state[_K1] = max(state[_K1], _MIN_GAIN)
        state[_K2] = max(state[_K2], _MIN_GAIN)
        state[_TAU1] = max(state[_TAU1], _MIN_TAU_DAYS)
        state[_TAU2] = max(state[_TAU2], _MIN_TAU_DAYS)

    @staticmethod
    def _transition(state: np.ndarray, load: float) -> np.ndarray:
        g, h, k1, k2, tau1, tau2 = state
        return np.array(
            [
                g * math.exp(-1.0 / tau1) + load,
                h * math.exp(-1.0 / tau2) + load,
                k1,
                k2,
                tau1,
                tau2,
            ],
            dtype=float,
        )

    @staticmethod
    def _transition_jacobian(state: np.ndarray) -> np.ndarray:
        g, h, _, _, tau1, tau2 = state
        decay1 = math.exp(-1.0 / tau1)
        decay2 = math.exp(-1.0 / tau2)
        jacobian = np.eye(_STATE_SIZE)
        jacobian[_G, _G] = decay1
        jacobian[_G, _TAU1] = g * decay1 / (tau1 * tau1)
        jacobian[_H, _H] = decay2
        jacobian[_H, _TAU2] = h * decay2 / (tau2 * tau2)
        return jacobian

    def _measurement(self, state: np.ndarray) -> float:
        g, h, k1, k2, _, _ = state
        return float(self._p0 + k1 * g - k2 * h)

    def _measurement_jacobian(self, state: np.ndarray) -> np.ndarray:
        g, h, k1, k2, _, _ = state
        return np.array([[k1, -k2, g, -h, 0.0, 0.0]], dtype=float)
