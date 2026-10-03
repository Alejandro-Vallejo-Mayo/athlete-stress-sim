"""Parser for Polar FIT files using ``fitparse``.

Extracts the ``session`` summary and the per-second ``record`` stream (heart
rate, speed, cadence, altitude, distance) and normalizes it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fitparse import FitFile

from athlete_stress_sim.core.etl.normalize import normalize_records
from athlete_stress_sim.core.etl.types import (
    ParsedSession,
    RawRecord,
    SessionMetadata,
)


class FITParser:
    """Parse a FIT file into a :class:`ParsedSession`."""

    def parse(self, path: Path | str) -> ParsedSession:
        """Read and normalize a FIT file.

        Args:
            path: Path to the ``.fit`` file.

        Returns:
            The parsed session with metadata and normalized samples.
        """
        fit = FitFile(str(path))
        metadata = SessionMetadata()
        records: list[RawRecord] = []
        for message in fit.get_messages():
            if message.name == "session":
                metadata = _parse_session(message)
            elif message.name == "record":
                records.append(_parse_record(message))
        return ParsedSession(metadata=metadata, samples=normalize_records(records))


def _fields(message: Any) -> dict[str, Any]:
    return {field.name: field.value for field in message.fields}


def _number(fields: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = fields.get(name)
        if value is not None:
            return float(value)
    return None


def _integer(fields: dict[str, Any], *names: str) -> int | None:
    value = _number(fields, *names)
    return None if value is None else int(round(value))


def _text(fields: dict[str, Any], name: str) -> str:
    value = fields.get(name)
    return "" if value is None else str(value)


def _parse_record(message: Any) -> RawRecord:
    fields = _fields(message)
    return RawRecord(
        timestamp=fields.get("timestamp"),
        hr=_number(fields, "heart_rate"),
        speed_mps=_number(fields, "enhanced_speed", "speed"),
        cadence=_number(fields, "enhanced_cadence", "cadence"),
        altitude_m=_number(fields, "enhanced_altitude", "altitude"),
        distance_m=_number(fields, "distance"),
    )


def _parse_session(message: Any) -> SessionMetadata:
    fields = _fields(message)
    return SessionMetadata(
        sport=_text(fields, "sport"),
        sub_sport=_text(fields, "sub_sport"),
        start_time=fields.get("start_time"),
        duration_s=_number(fields, "total_elapsed_time", "total_timer_time"),
        distance_m=_number(fields, "total_distance"),
        calories=_number(fields, "total_calories"),
        avg_hr=_integer(fields, "avg_heart_rate"),
        max_hr=_integer(fields, "max_heart_rate"),
        total_ascent_m=_number(fields, "total_ascent"),
        total_descent_m=_number(fields, "total_descent"),
    )
