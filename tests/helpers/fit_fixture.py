"""Build minimal, valid FIT files in memory for tests.

Encodes a ``file_id``, a ``session`` and a ``record`` stream without shipping
any real biometric data (``RNF-01``). Only the fields the parser reads are
written.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# FIT base types (high bit set => little endian).
_ENUM = 0x00
_UINT8 = 0x02
_UINT16 = 0x84
_UINT32 = 0x86

_FIT_EPOCH = datetime(1989, 12, 31)

# CRC-16 table from the FIT SDK.
_CRC_TABLE = [
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
]


@dataclass(frozen=True)
class RecordSpec:
    """One ``record`` message to encode."""

    timestamp: datetime
    hr: int = 0
    speed_mps: float = 0.0
    cadence: int = 0
    altitude_m: float = 0.0
    distance_m: float = 0.0


def _fit_timestamp(moment: datetime) -> int:
    return int((moment - _FIT_EPOCH).total_seconds())


def _crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def _definition(local_type: int, global_num: int, fields: Sequence[tuple[int, int]]) -> bytes:
    header = 0x40 | local_type
    out = bytearray([header, 0x00, 0x00])
    out += struct.pack("<H", global_num)
    out.append(len(fields))
    for field_num, base_type in fields:
        size = _base_type_size(base_type)
        out += bytes([field_num, size, base_type])
    return bytes(out)


def _base_type_size(base_type: int) -> int:
    kind = base_type & 0x1F
    return {0x00: 1, 0x02: 1, 0x04: 2, 0x06: 4}[kind]


def _data(local_type: int, payload: bytes) -> bytes:
    return bytes([local_type]) + payload


def build_activity_fit(
    records: Sequence[RecordSpec],
    sport: int = 1,
    sub_sport: int = 0,
    total_calories: int = 500,
) -> bytes:
    """Encode a minimal FIT activity file with the given records.

    Args:
        records: Ordered per-second records.
        sport: FIT sport enum (``1`` = running).
        sub_sport: FIT sub-sport enum (``0`` = generic).
        total_calories: Session calorie total.

    Returns:
        The raw FIT file bytes.
    """
    body = bytearray()

    # file_id (global 0): type = activity (4).
    body += _definition(0, 0, [(0, _ENUM)])
    body += _data(0, struct.pack("<B", 4))

    # session (global 18).
    session_fields = [
        (253, _UINT32),  # timestamp
        (2, _UINT32),  # start_time
        (5, _ENUM),  # sport
        (6, _ENUM),  # sub_sport
        (7, _UINT32),  # total_elapsed_time (scale 1000)
        (9, _UINT32),  # total_distance (scale 100)
        (11, _UINT16),  # total_calories
        (16, _UINT8),  # avg_heart_rate
        (17, _UINT8),  # max_heart_rate
    ]
    body += _definition(0, 18, session_fields)

    start = records[0].timestamp
    end = records[-1].timestamp
    elapsed = int((end - start).total_seconds())
    distance = records[-1].distance_m
    hrs = [r.hr for r in records if r.hr > 0]
    avg_hr = int(sum(hrs) / len(hrs)) if hrs else 0
    max_hr = max(hrs) if hrs else 0
    body += _data(
        0,
        struct.pack(
            "<IIBBIIHBB",
            _fit_timestamp(end),
            _fit_timestamp(start),
            sport,
            sub_sport,
            elapsed * 1000,
            int(distance * 100),
            total_calories,
            avg_hr,
            max_hr,
        ),
    )

    # record (global 20).
    record_fields = [
        (253, _UINT32),  # timestamp
        (3, _UINT8),  # heart_rate
        (4, _UINT8),  # cadence
        (73, _UINT32),  # enhanced_speed (scale 1000)
        (78, _UINT32),  # enhanced_altitude (scale 5, offset 500)
        (5, _UINT32),  # distance (scale 100)
    ]
    body += _definition(0, 20, record_fields)
    for record in records:
        body += _data(
            0,
            struct.pack(
                "<IBBII",
                _fit_timestamp(record.timestamp),
                record.hr,
                record.cadence,
                int(round(record.speed_mps * 1000)),
                int(round((record.altitude_m + 500) * 5)),
            )
            + struct.pack("<I", int(round(record.distance_m * 100))),
        )

    return _wrap(body)


def write_activity_fit(
    path: Path,
    records: Sequence[RecordSpec],
    sport: int = 1,
    sub_sport: int = 0,
    total_calories: int = 500,
) -> Path:
    """Encode a FIT activity and write it to ``path``."""
    path.write_bytes(build_activity_fit(records, sport, sub_sport, total_calories))
    return path


def _wrap(body: bytes) -> bytes:
    header_size = 14
    header = struct.pack(
        "<BBHI4s",
        header_size,
        0x20,
        2140,
        len(body),
        b".FIT",
    )
    header_crc = _crc(header)
    header += struct.pack("<H", header_crc)
    file_without_crc = header + body
    return file_without_crc + struct.pack("<H", _crc(file_without_crc))
