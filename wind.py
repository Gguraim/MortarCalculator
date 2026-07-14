"""Wind model for mortar firing corrections."""

from __future__ import annotations

import math
from dataclasses import dataclass

MILS_PER_RADIAN = 6400.0 / (2.0 * math.pi)
DRAG_RESPONSE_SECONDS = 0.18
HEADWIND_RANGE_RESPONSE = 0.035


@dataclass(frozen=True, slots=True)
class WindSolution:
    """Computed wind components and fire-control corrections."""

    crosswind: float
    headwind: float
    azimuth_correction: float
    range_correction: float


def _relative_angle(wind_from_degrees: float, shot_azimuth_degrees: float) -> float:
    wind_to = (wind_from_degrees + 180.0) % 360.0
    return math.radians((wind_to - shot_azimuth_degrees + 540.0) % 360.0 - 180.0)


def calculate_crosswind(
    wind_speed: float,
    wind_direction: float,
    shot_azimuth: float,
) -> float:
    """Return signed crosswind in m/s; positive pushes impact right."""
    return wind_speed * math.sin(_relative_angle(wind_direction, shot_azimuth))


def calculate_headwind(
    wind_speed: float,
    wind_direction: float,
    shot_azimuth: float,
) -> float:
    """Return signed headwind in m/s; positive opposes the projectile."""
    return -wind_speed * math.cos(_relative_angle(wind_direction, shot_azimuth))


def calculate_drift(crosswind: float, range_m: float, flight_time: float) -> float:
    """Estimate wind drift using time of flight and aerodynamic lag."""
    response = 1.0 - math.exp(-max(flight_time, 0.0) * DRAG_RESPONSE_SECONDS)
    return crosswind * flight_time * response


def calculate_wind_solution(
    wind_speed: float,
    wind_direction: float,
    shot_azimuth: float,
    range_m: float,
    flight_time: float,
) -> WindSolution:
    """Calculate crosswind, headwind, deflection, and range corrections."""
    crosswind = calculate_crosswind(wind_speed, wind_direction, shot_azimuth)
    headwind = calculate_headwind(wind_speed, wind_direction, shot_azimuth)
    drift = calculate_drift(crosswind, range_m, flight_time)
    azimuth_correction = -(drift / max(range_m, 1.0)) * MILS_PER_RADIAN
    range_correction = headwind * flight_time * HEADWIND_RANGE_RESPONSE
    return WindSolution(crosswind, headwind, azimuth_correction, range_correction)
