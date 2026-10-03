"""Normalization and validation of raw FIT records.

Turns raw per-second records into :class:`Sample` objects, flagging outliers as
invalid (without dropping them, so gaps remain visible) and offering gap
detection for downstream metrics.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median

from athlete_stress_sim.core.etl.types import RawRecord, Sample

HR_MIN = 25
HR_MAX = 240
CADENCE_MAX = 250
SPEED_MAX_MPS = 15.0  # ~54 km/h: above this a running sample is not credible.
ALTITUDE_MIN_M = -500.0
ALTITUDE_MAX_M = 9000.0
_MIN_GAP_DETECTION_SAMPLES = 3


def normalize_records(records: list[RawRecord]) -> list[Sample]:
    """Sort, timestamp and validate raw records into clean samples.

    Args:
        records: Raw records read from a FIT file (timestamp may be missing).

    Returns:
        Samples ordered by timestamp. Out-of-range values are nulled and the
        sample is flagged with ``is_valid=False`` instead of being dropped.
    """
    timed = sorted((r for r in records if r.timestamp is not None), key=_timestamp)
    if not timed:
        return []

    start = _timestamp(timed[0])
    samples: list[Sample] = []
    for record in timed:
        timestamp = _timestamp(record)
        is_valid = True

        hr = _as_int(record.hr)
        if hr is not None and not HR_MIN <= hr <= HR_MAX:
            hr, is_valid = None, False

        cadence = _as_int(record.cadence)
        if cadence is not None and not 0 <= cadence <= CADENCE_MAX:
            cadence, is_valid = None, False

        speed = record.speed_mps
        if speed is not None and not 0.0 <= speed <= SPEED_MAX_MPS:
            speed, is_valid = None, False

        altitude = record.altitude_m
        if altitude is not None and not ALTITUDE_MIN_M <= altitude <= ALTITUDE_MAX_M:
            altitude, is_valid = None, False

        samples.append(
            Sample(
                timestamp=timestamp,
                elapsed_s=(timestamp - start).total_seconds(),
                hr=hr,
                speed_mps=speed,
                cadence=cadence,
                altitude_m=altitude,
                distance_m=record.distance_m,
                is_valid=is_valid,
            )
        )
    return samples


def find_gaps(
    samples: list[Sample],
    factor: float = 2.0,
) -> list[tuple[datetime, datetime]]:
    """Return timestamp pairs where the interval exceeds ``factor`` times the median."""
    if len(samples) < _MIN_GAP_DETECTION_SAMPLES:
        return []
    deltas = [
        (samples[i].timestamp - samples[i - 1].timestamp).total_seconds()
        for i in range(1, len(samples))
    ]
    reference = median(deltas)
    if reference <= 0:
        return []
    threshold = reference * factor
    return [
        (samples[i - 1].timestamp, samples[i].timestamp)
        for i, delta in enumerate(deltas, start=1)
        if delta > threshold
    ]


def _timestamp(record: RawRecord) -> datetime:
    assert record.timestamp is not None
    return record.timestamp


def _as_int(value: float | None) -> int | None:
    return None if value is None else int(round(value))
