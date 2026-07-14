"""박격포 사격 보정을 위한 풍향/풍속 모델."""

from __future__ import annotations

import math
from dataclasses import dataclass

MILS_PER_RADIAN = 6400.0 / (2.0 * math.pi)
DRAG_RESPONSE_SECONDS = 0.18
HEADWIND_RANGE_RESPONSE = 0.035


@dataclass(frozen=True, slots=True)
class WindSolution:
    """계산된 바람 성분과 사격 통제 보정값."""

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
    """부호가 있는 횡풍을 m/s 단위로 반환합니다.

    양수는 탄착을 오른쪽으로 밀어냅니다.
    """
    return wind_speed * math.sin(_relative_angle(wind_direction, shot_azimuth))


def calculate_headwind(
    wind_speed: float,
    wind_direction: float,
    shot_azimuth: float,
) -> float:
    """부호가 있는 역풍을 m/s 단위로 반환합니다.

    양수는 탄체 진행을 방해합니다.
    """
    return -wind_speed * math.cos(_relative_angle(wind_direction, shot_azimuth))


def calculate_drift(crosswind: float, range_m: float, flight_time: float) -> float:
    """비행시간과 공기역학적 지연을 사용해 풍편을 추정합니다."""
    response = 1.0 - math.exp(-max(flight_time, 0.0) * DRAG_RESPONSE_SECONDS)
    return crosswind * flight_time * response


def calculate_wind_solution(
    wind_speed: float,
    wind_direction: float,
    shot_azimuth: float,
    range_m: float,
    flight_time: float,
) -> WindSolution:
    """횡풍, 역풍, 편각 보정, 거리 보정을 계산합니다."""
    crosswind = calculate_crosswind(wind_speed, wind_direction, shot_azimuth)
    headwind = calculate_headwind(wind_speed, wind_direction, shot_azimuth)
    drift = calculate_drift(crosswind, range_m, flight_time)
    azimuth_correction = -(drift / max(range_m, 1.0)) * MILS_PER_RADIAN
    range_correction = headwind * flight_time * HEADWIND_RANGE_RESPONSE
    return WindSolution(crosswind, headwind, azimuth_correction, range_correction)
