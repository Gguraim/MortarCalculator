"""탄도 보간 및 사격 제원 생성."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import interp1d

DATA_PATH = Path("data/m821.json")
MILS_PER_RADIAN = 6400.0 / (2.0 * math.pi)


@dataclass(frozen=True, slots=True)
class ChargeTable:
    """박격포 장약 하나에 대한 보간기."""

    charge: int
    ranges: np.ndarray
    mil: interp1d
    time: interp1d
    elevation_correction: interp1d
    dispersion: interp1d


@dataclass(frozen=True, slots=True)
class FiringSolution:
    """장약 하나에 대한 비보정 및 보정 사격 제원 전체."""

    charge: int
    range_m: float
    elevation_mil: float
    corrected_elevation_mil: float
    flight_time: float
    dispersion: float
    elevation_correction: float


def load_ballistic_data(path: Path = DATA_PATH) -> dict[int, ChargeTable]:
    """JSON에서 M821 장약표를 불러와 scipy 보간기를 생성합니다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {entry["charge"]: _build_charge_table(entry) for entry in raw["charges"]}


def _build_charge_table(entry: dict) -> ChargeTable:
    points = sorted(entry["points"], key=lambda item: item["range"])
    ranges = np.array([point["range"] for point in points], dtype=float)
    return ChargeTable(
        charge=int(entry["charge"]),
        ranges=ranges,
        mil=_interpolator(ranges, points, "mil"),
        time=_interpolator(ranges, points, "time"),
        elevation_correction=_interpolator(ranges, points, "elevation_correction"),
        dispersion=_interpolator(ranges, points, "dispersion"),
    )


def _interpolator(ranges: np.ndarray, points: list[dict], key: str) -> interp1d:
    values = np.array([point[key] for point in points], dtype=float)
    return interp1d(ranges, values, kind="linear", bounds_error=True)


def calculate_elevation(table: ChargeTable, range_m: float) -> float:
    """사거리에 대한 사각을 밀 단위로 보간합니다."""
    return float(table.mil(range_m))


def calculate_flight_time(table: ChargeTable, range_m: float) -> float:
    """탄체 비행시간을 초 단위로 보간합니다."""
    return float(table.time(range_m))


def calculate_dispersion(table: ChargeTable, range_m: float) -> float:
    """예상 탄착 분산을 미터 단위로 보간합니다."""
    return float(table.dispersion(range_m))


def apply_elevation_correction(
    elevation_mil: float,
    elevation_difference: float,
    range_m: float,
) -> float:
    """목표 고도차에 대한 수직각 보정을 적용합니다."""
    vertical_angle = math.atan2(elevation_difference, max(range_m, 1.0))
    return elevation_mil + vertical_angle * MILS_PER_RADIAN


def recommend_valid_charges(
    tables: dict[int, ChargeTable],
    range_m: float,
) -> list[int]:
    """요청 사거리를 포함하는 표를 가진 장약을 반환합니다."""
    return [
        charge
        for charge, table in sorted(tables.items())
        if _in_range(table, range_m)
    ]


def calculate_solution(
    table: ChargeTable,
    range_m: float,
    elevation_difference: float = 0.0,
) -> FiringSolution:
    """유효한 장약 하나에 대한 사격 제원을 계산합니다."""
    elevation = calculate_elevation(table, range_m)
    table_correction = float(table.elevation_correction(range_m))
    corrected = apply_elevation_correction(
        elevation + table_correction,
        elevation_difference,
        range_m,
    )
    return FiringSolution(
        charge=table.charge,
        range_m=range_m,
        elevation_mil=elevation,
        corrected_elevation_mil=corrected,
        flight_time=calculate_flight_time(table, range_m),
        dispersion=calculate_dispersion(table, range_m),
        elevation_correction=corrected - elevation,
    )


def get_all_firing_solutions(
    range_m: float,
    elevation_difference: float = 0.0,
    tables: dict[int, ChargeTable] | None = None,
) -> list[FiringSolution]:
    """요청된 기하 조건에 대한 모든 유효 장약 제원을 반환합니다."""
    loaded_tables = tables or load_ballistic_data()
    return [
        calculate_solution(loaded_tables[charge], range_m, elevation_difference)
        for charge in recommend_valid_charges(loaded_tables, range_m)
    ]


def _in_range(table: ChargeTable, range_m: float) -> bool:
    return float(table.ranges.min()) <= range_m <= float(table.ranges.max())
