"""Ballistic interpolation and firing solution generation."""

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
    """Interpolators for one mortar charge."""

    charge: int
    ranges: np.ndarray
    mil: interp1d
    time: interp1d
    elevation_correction: interp1d
    dispersion: interp1d


@dataclass(frozen=True, slots=True)
class FiringSolution:
    """A complete uncorrected and corrected solution for one charge."""

    charge: int
    range_m: float
    elevation_mil: float
    corrected_elevation_mil: float
    flight_time: float
    dispersion: float
    elevation_correction: float


def load_ballistic_data(path: Path = DATA_PATH) -> dict[int, ChargeTable]:
    """Load M821 charge tables from JSON and build scipy interpolators."""
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
    """Interpolate quadrant elevation in mils for a range."""
    return float(table.mil(range_m))


def calculate_flight_time(table: ChargeTable, range_m: float) -> float:
    """Interpolate projectile time of flight in seconds."""
    return float(table.time(range_m))


def calculate_dispersion(table: ChargeTable, range_m: float) -> float:
    """Interpolate estimated impact dispersion in meters."""
    return float(table.dispersion(range_m))


def apply_elevation_correction(
    elevation_mil: float,
    elevation_difference: float,
    range_m: float,
) -> float:
    """Apply vertical-angle correction for target altitude difference."""
    vertical_angle = math.atan2(elevation_difference, max(range_m, 1.0))
    return elevation_mil + vertical_angle * MILS_PER_RADIAN


def recommend_valid_charges(
    tables: dict[int, ChargeTable],
    range_m: float,
) -> list[int]:
    """Return charges whose table brackets the requested range."""
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
    """Calculate the firing solution for one valid charge."""
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
    """Return every valid charge solution for the requested geometry."""
    loaded_tables = tables or load_ballistic_data()
    return [
        calculate_solution(loaded_tables[charge], range_m, elevation_difference)
        for charge in recommend_valid_charges(loaded_tables, range_m)
    ]


def _in_range(table: ChargeTable, range_m: float) -> bool:
    return float(table.ranges.min()) <= range_m <= float(table.ranges.max())
