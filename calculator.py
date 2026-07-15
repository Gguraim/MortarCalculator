"""Arma Reforger M252/M821 박격포 계산기."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

BALLISTICS_PATH = Path("ballistics.json")
MILS_PER_CIRCLE = 6400.0
DEGREES_PER_CIRCLE = 360.0
MILS_PER_RADIAN = MILS_PER_CIRCLE / (2.0 * math.pi)
WIND_RESPONSE_HALF_TIME = 4.0


@dataclass(frozen=True, slots=True)
class Grid:
    """지도 격자 좌표와 고도."""

    easting: float
    northing: float
    elevation: float = 0.0


@dataclass(frozen=True, slots=True)
class BallisticPoint:
    """탄도표의 단일 사거리 지점."""

    range_m: float
    mil: float
    time: float
    dispersion: float


@dataclass(frozen=True, slots=True)
class FiringSolution:
    """장약 하나에 대한 사격 제원."""

    charge: int
    elevation_mil: float
    corrected_elevation_mil: float
    time_of_flight: float
    dispersion: float
    wind_correction_mil: float
    corrected_azimuth_mil: float
    elevation_wind_correction_mil: float


@dataclass(frozen=True, slots=True)
class WindResult:
    """풍향/풍속 보정 결과."""

    crosswind: float
    headwind: float
    tailwind: float
    drift_m: float
    range_effect_m: float
    azimuth_correction_mil: float
    elevation_correction_mil: float


def interpolate(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    """두 지점 사이의 선형 보간값을 반환합니다."""
    if x1 == x0:
        return y0
    ratio = (x - x0) / (x1 - x0)
    return y0 + ratio * (y1 - y0)


def load_ballistics(path: Path = BALLISTICS_PATH) -> dict[int, list[BallisticPoint]]:
    """JSON 탄도표를 불러옵니다."""
    data = json.loads(path.read_text(encoding="utf-8"))
    tables: dict[int, list[BallisticPoint]] = {}
    for charge in data["charges"]:
        tables[int(charge["charge"])] = [
            BallisticPoint(
                range_m=float(point["range"]),
                mil=float(point["mil"]),
                time=float(point["time"]),
                dispersion=float(point["dispersion"]),
            )
            for point in charge["points"]
        ]
    return tables


def bracket_points(
    points: list[BallisticPoint],
    range_m: float,
) -> tuple[BallisticPoint, BallisticPoint] | None:
    """사거리를 감싸는 두 탄도표 지점을 찾습니다."""
    ordered = sorted(points, key=lambda point: point.range_m)
    if range_m < ordered[0].range_m or range_m > ordered[-1].range_m:
        return None
    for left, right in zip(ordered, ordered[1:]):
        if left.range_m <= range_m <= right.range_m:
            return left, right
    return ordered[-1], ordered[-1]


def interpolate_point(
    points: list[BallisticPoint],
    range_m: float,
) -> BallisticPoint | None:
    """사각, 비행시간, 분산을 사거리 기준으로 보간합니다."""
    bracket = bracket_points(points, range_m)
    if bracket is None:
        return None
    left, right = bracket
    return BallisticPoint(
        range_m=range_m,
        mil=interpolate(range_m, left.range_m, left.mil, right.range_m, right.mil),
        time=interpolate(range_m, left.range_m, left.time, right.range_m, right.time),
        dispersion=interpolate(
            range_m,
            left.range_m,
            left.dispersion,
            right.range_m,
            right.dispersion,
        ),
    )


def parse_grid(value: str) -> Grid:
    """10자리 격자 또는 쉼표 구분 좌표를 해석합니다."""
    text = value.strip().replace(" ", "")
    if "," in text:
        easting, northing = text.split(",", maxsplit=1)
        return Grid(float(easting), float(northing))
    if len(text) != 10 or not text.isdigit():
        raise ValueError("격자는 10자리 숫자 또는 '동,북' 형식이어야 합니다.")
    return Grid(float(text[:5]), float(text[5:]))


def prompt_grid(label: str) -> Grid:
    """사용자에게 격자 좌표를 입력받습니다."""
    while True:
        try:
            return parse_grid(input(f"{label}\n> "))
        except ValueError as exc:
            print(f"잘못된 입력입니다: {exc}")


def prompt_float(label: str) -> float:
    """사용자에게 숫자 값을 입력받습니다."""
    while True:
        try:
            return float(input(f"{label}\n> ").strip())
        except ValueError:
            print("잘못된 입력입니다. 숫자를 입력하세요.")


def distance_between(mortar: Grid, target: Grid) -> float:
    """박격포와 목표 사이의 수평 거리를 계산합니다."""
    return math.hypot(
        target.easting - mortar.easting,
        target.northing - mortar.northing,
    )


def azimuth_degrees(mortar: Grid, target: Grid) -> float:
    """박격포에서 목표까지의 방향각을 도 단위로 계산합니다."""
    dx = target.easting - mortar.easting
    dy = target.northing - mortar.northing
    return math.degrees(math.atan2(dx, dy)) % DEGREES_PER_CIRCLE


def degrees_to_mils(degrees: float) -> float:
    """도 단위 방향각을 밀 단위로 변환합니다."""
    return degrees * MILS_PER_CIRCLE / DEGREES_PER_CIRCLE


def elevation_difference(mortar: Grid, target: Grid) -> float:
    """목표 고도에서 박격포 고도를 뺀 고도차를 반환합니다."""
    return target.elevation - mortar.elevation


def elevation_angle_mil(elevation_delta: float, range_m: float) -> float:
    """고도차에 따른 사각 보정을 밀 단위로 계산합니다."""
    return math.atan2(elevation_delta, max(range_m, 1.0)) * MILS_PER_RADIAN


def wind_response(time_of_flight: float) -> float:
    """비행시간 기반 바람 반응 비율을 계산합니다."""
    return 1.0 - math.pow(0.5, max(time_of_flight, 0.0) / WIND_RESPONSE_HALF_TIME)


def wind_components(
    wind_direction: float,
    wind_speed: float,
    azimuth: float,
) -> tuple[float, float, float]:
    """횡풍, 역풍, 순풍 성분을 계산합니다."""
    wind_to = (wind_direction + 180.0) % DEGREES_PER_CIRCLE
    relative = math.radians((wind_to - azimuth + 540.0) % 360.0 - 180.0)
    crosswind = wind_speed * math.sin(relative)
    along = wind_speed * math.cos(relative)
    headwind = max(-along, 0.0)
    tailwind = max(along, 0.0)
    return crosswind, headwind, tailwind


def calculate_wind(
    wind_direction: float,
    wind_speed: float,
    azimuth: float,
    range_m: float,
    time_of_flight: float,
) -> WindResult:
    """비행시간을 사용해 바람 보정을 계산합니다."""
    response = wind_response(time_of_flight)
    crosswind, headwind, tailwind = wind_components(
        wind_direction,
        wind_speed,
        azimuth,
    )
    drift_m = crosswind * time_of_flight * response
    range_effect_m = (tailwind - headwind) * time_of_flight * response
    azimuth_correction = -(drift_m / max(range_m, 1.0)) * MILS_PER_RADIAN
    elevation_correction = -(range_effect_m / max(range_m, 1.0)) * MILS_PER_RADIAN
    return WindResult(
        crosswind=crosswind,
        headwind=headwind,
        tailwind=tailwind,
        drift_m=drift_m,
        range_effect_m=range_effect_m,
        azimuth_correction_mil=azimuth_correction,
        elevation_correction_mil=elevation_correction,
    )


def firing_solution(
    charge: int,
    point: BallisticPoint,
    range_m: float,
    azimuth_mil: float,
    elevation_delta: float,
    wind: WindResult,
) -> FiringSolution:
    """보정된 단일 장약 사격 제원을 생성합니다."""
    terrain_correction = elevation_angle_mil(elevation_delta, range_m)
    corrected_elevation = point.mil + terrain_correction + wind.elevation_correction_mil
    corrected_azimuth = (azimuth_mil + wind.azimuth_correction_mil) % MILS_PER_CIRCLE
    return FiringSolution(
        charge=charge,
        elevation_mil=point.mil,
        corrected_elevation_mil=corrected_elevation,
        time_of_flight=point.time,
        dispersion=point.dispersion,
        wind_correction_mil=wind.azimuth_correction_mil,
        corrected_azimuth_mil=corrected_azimuth,
        elevation_wind_correction_mil=wind.elevation_correction_mil,
    )


def recommend_solutions(
    tables: dict[int, list[BallisticPoint]],
    range_m: float,
    azimuth: float,
    elevation_delta: float,
    wind_direction: float,
    wind_speed: float,
) -> list[tuple[FiringSolution, WindResult]]:
    """사용 가능한 모든 장약의 사격 제원을 계산합니다."""
    azimuth_mil = degrees_to_mils(azimuth)
    solutions: list[tuple[FiringSolution, WindResult]] = []
    for charge, points in sorted(tables.items()):
        point = interpolate_point(points, range_m)
        if point is None:
            continue
        wind = calculate_wind(wind_direction, wind_speed, azimuth, range_m, point.time)
        solution = firing_solution(
            charge,
            point,
            range_m,
            azimuth_mil,
            elevation_delta,
            wind,
        )
        solutions.append((solution, wind))
    return solutions


def apply_fire_correction(
    target: Grid,
    azimuth: float,
    correction: str,
) -> Grid:
    """LEFT/RIGHT/ADD/DROP 사격 수정을 목표 좌표에 적용합니다."""
    parts = correction.strip().upper().split()
    if len(parts) != 2 or parts[0] not in {"LEFT", "RIGHT", "ADD", "DROP"}:
        raise ValueError("LEFT 20, RIGHT 10, ADD 50, DROP 30 형식으로 입력하세요.")
    amount = float(parts[1])
    forward = math.radians(azimuth)
    right = math.radians(azimuth + 90.0)
    if parts[0] == "ADD":
        angle, distance = forward, amount
    elif parts[0] == "DROP":
        angle, distance = forward, -amount
    elif parts[0] == "RIGHT":
        angle, distance = right, amount
    else:
        angle, distance = right, -amount
    return Grid(
        easting=target.easting + math.sin(angle) * distance,
        northing=target.northing + math.cos(angle) * distance,
        elevation=target.elevation,
    )


def print_summary(
    mortar: Grid,
    target: Grid,
    wind_direction: float,
    wind_speed: float,
    solutions: list[tuple[FiringSolution, WindResult]],
) -> None:
    """계산 결과를 콘솔에 표시합니다."""
    range_m = distance_between(mortar, target)
    azimuth = azimuth_degrees(mortar, target)
    elevation_delta = elevation_difference(mortar, target)
    print("\n" + "=" * 40)
    print(f"박격포 위치: 동 {mortar.easting:.0f} 북 {mortar.northing:.0f}")
    print(f"목표 위치:   동 {target.easting:.0f} 북 {target.northing:.0f}")
    print(f"풍향: {wind_direction:.0f}°")
    print(f"풍속: {wind_speed:.1f} m/s")
    print(f"거리: {range_m:.1f} m")
    print(f"방향각: {azimuth:.1f}° / {degrees_to_mils(azimuth):.0f} mil")
    print(f"고도차: {elevation_delta:+.1f} m")
    print("=" * 40)
    if not solutions:
        print("사용 가능한 사격 제원이 없습니다. 사거리 밖입니다.")
        print("=" * 40)
        return
    solution, wind = solutions[0]
    print(f"추천 장약: {solution.charge}")
    print(f"사각: {solution.elevation_mil:.1f} mil")
    print(f"보정 사각: {solution.corrected_elevation_mil:.1f} mil")
    print(f"보정 방향각: {solution.corrected_azimuth_mil:.0f} mil")
    print(f"비행시간: {solution.time_of_flight:.1f} s")
    print(f"분산: ±{solution.dispersion:.1f} m")
    print(f"횡풍: {wind.crosswind:+.1f} m/s")
    print(f"역풍: {wind.headwind:+.1f} m/s")
    print(f"순풍: {wind.tailwind:+.1f} m/s")
    print(f"풍편: {wind.drift_m:+.1f} m")
    print(f"풍향 보정: {solution.wind_correction_mil:+.1f} mil")
    print(f"풍속 사각 보정: {solution.elevation_wind_correction_mil:+.1f} mil")
    print("=" * 40)


def print_all_solutions(solutions: list[tuple[FiringSolution, WindResult]]) -> None:
    """추천 외 장약 제원을 간단히 표시합니다."""
    if len(solutions) <= 1:
        return
    print("추가 사용 가능 장약")
    for solution, _wind in solutions[1:]:
        print(
            f"  장약 {solution.charge}: "
            f"사각 {solution.corrected_elevation_mil:.1f} mil, "
            f"비행시간 {solution.time_of_flight:.1f} s, "
            f"분산 ±{solution.dispersion:.1f} m"
        )


def calculate_and_display(
    tables: dict[int, list[BallisticPoint]],
    mortar: Grid,
    target: Grid,
    wind_direction: float,
    wind_speed: float,
) -> list[tuple[FiringSolution, WindResult]]:
    """현재 입력값으로 계산하고 결과를 출력합니다."""
    range_m = distance_between(mortar, target)
    azimuth = azimuth_degrees(mortar, target)
    elevation_delta = elevation_difference(mortar, target)
    solutions = recommend_solutions(
        tables,
        range_m,
        azimuth,
        elevation_delta,
        wind_direction,
        wind_speed,
    )
    print_summary(mortar, target, wind_direction, wind_speed, solutions)
    print_all_solutions(solutions)
    return solutions


def main() -> None:
    """대화형 박격포 계산기를 실행합니다."""
    tables = load_ballistics()
    print("Arma Reforger M252 / M821 박격포 계산기")
    mortar_grid = prompt_grid("박격포 격자")
    target_grid = prompt_grid("목표 격자")
    mortar = Grid(mortar_grid.easting, mortar_grid.northing, prompt_float("박격포 고도"))
    target = Grid(target_grid.easting, target_grid.northing, prompt_float("목표 고도"))
    wind_direction = prompt_float("풍향") % DEGREES_PER_CIRCLE
    wind_speed = prompt_float("풍속")
    while True:
        calculate_and_display(tables, mortar, target, wind_direction, wind_speed)
        correction = input("사격 수정(LEFT/RIGHT/ADD/DROP, 종료는 Enter)\n> ").strip()
        if not correction:
            print("종료")
            return
        try:
            azimuth = azimuth_degrees(mortar, target)
            target = apply_fire_correction(target, azimuth, correction)
        except ValueError as exc:
            print(f"잘못된 입력입니다: {exc}")


if __name__ == "__main__":
    main()
