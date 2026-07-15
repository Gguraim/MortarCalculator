"""Arma Reforger M252/M821 박격포 계산기."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

BALLISTICS_PATH = Path("ballistics.json")
MILS_PER_CIRCLE = 6400.0
DEGREES_PER_CIRCLE = 360.0
MILS_PER_RADIAN = MILS_PER_CIRCLE / (2.0 * math.pi)
WIND_RESPONSE_HALF_TIME = 4.0
T = TypeVar("T")


class RestartRequest(Exception):
    """입력을 처음부터 다시 시작하기 위한 내부 신호."""


class QuitRequest(Exception):
    """프로그램을 즉시 종료하기 위한 내부 신호."""


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
        raise ValueError
    return Grid(float(text[:5]), float(text[5:]))


def read_controlled_input(label: str) -> str:
    """R/Q 제어 입력을 공통 처리하고 원문 입력값을 반환합니다."""
    value = input(f"{label}\n> ").strip()
    command = value.upper()
    if command == "R":
        raise RestartRequest
    if command == "Q":
        raise QuitRequest
    return value


def input_value(label: str, parser: Callable[[str], T]) -> T:
    """공통 검증 루프를 통해 값을 입력받습니다."""
    while True:
        try:
            return parser(read_controlled_input(label))
        except RestartRequest:
            raise
        except QuitRequest:
            raise
        except (TypeError, ValueError):
            print("잘못된 입력입니다.")
            print("다시 입력하세요.")


def input_grid(label: str) -> Grid:
    """R/Q와 검증을 지원하는 격자 입력 함수입니다."""
    return input_value(label, parse_grid)


def input_float(label: str) -> float:
    """R/Q와 검증을 지원하는 실수 입력 함수입니다."""
    return input_value(label, float)


def input_number(label: str) -> int:
    """R/Q와 검증을 지원하는 정수 입력 함수입니다."""
    return input_value(label, int)


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


@dataclass(frozen=True, slots=True)
class InputState:
    """현재 사격 계산 입력값."""

    mortar: Grid
    target: Grid
    wind_direction: float
    wind_speed: float


def input_mortar() -> Grid:
    """박격포 위치와 고도를 입력받습니다."""
    grid = input_grid("박격포 위치")
    elevation = input_float("박격포 고도")
    return Grid(grid.easting, grid.northing, elevation)


def input_target() -> Grid:
    """목표 위치와 고도를 입력받습니다."""
    grid = input_grid("목표 위치")
    elevation = input_float("목표 고도")
    return Grid(grid.easting, grid.northing, elevation)


def input_wind() -> tuple[float, float]:
    """풍향과 풍속을 입력받습니다."""
    direction = input_float("풍향") % DEGREES_PER_CIRCLE
    speed = input_float("풍속")
    return direction, speed


def input_all() -> InputState:
    """전체 입력 화면을 순서대로 처리합니다."""
    print("\n입력 화면")
    print("R: 전체 다시 입력 / Q: 종료")
    mortar = input_mortar()
    target = input_target()
    wind_direction, wind_speed = input_wind()
    return InputState(mortar, target, wind_direction, wind_speed)


def print_menu() -> str:
    """계산 후 주 메뉴를 표시하고 선택값을 반환합니다."""
    print("\n" + "=" * 40)
    print("[R] 전체 다시 입력")
    print("[T] 목표 위치만 변경")
    print("[W] 풍향/풍속만 변경")
    print("[M] 박격포 위치만 변경")
    print("[Q] 종료")
    print("=" * 40)
    return input("선택 : ").strip().upper()


def handle_menu_choice(state: InputState, choice: str) -> InputState | None:
    """주 메뉴 선택에 따라 필요한 입력만 갱신합니다."""
    if choice == "R":
        print("입력을 처음부터 다시 시작합니다.")
        raise RestartRequest
    if choice == "T":
        return InputState(
            state.mortar,
            input_target(),
            state.wind_direction,
            state.wind_speed,
        )
    if choice == "W":
        wind_direction, wind_speed = input_wind()
        return InputState(state.mortar, state.target, wind_direction, wind_speed)
    if choice == "M":
        return InputState(
            input_mortar(),
            state.target,
            state.wind_direction,
            state.wind_speed,
        )
    if choice == "Q":
        raise QuitRequest
    raise ValueError


def main() -> None:
    """대화형 박격포 계산기를 실행합니다."""
    tables = load_ballistics()
    print("Arma Reforger M252 / M821 박격포 계산기")
    state: InputState | None = None
    while True:
        try:
            if state is None:
                state = input_all()
            calculate_and_display(
                tables,
                state.mortar,
                state.target,
                state.wind_direction,
                state.wind_speed,
            )
            while True:
                try:
                    choice = print_menu()
                    state = handle_menu_choice(state, choice)
                    break
                except ValueError:
                    print("잘못된 입력입니다.")
                    print("다시 입력하세요.")
        except RestartRequest:
            state = None
            print("입력을 처음부터 다시 시작합니다.")
        except QuitRequest:
            print("프로그램을 종료합니다.")
            return
        except EOFError:
            print("프로그램을 종료합니다.")
            return


if __name__ == "__main__":
    main()
