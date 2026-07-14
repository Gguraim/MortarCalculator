"""Arma Reforger M252 사격 통제 시스템용 전문 콘솔 UI."""

from __future__ import annotations

import math
from dataclasses import replace

from ballistics import FiringSolution, get_all_firing_solutions, load_ballistic_data
from config import AppConfig, Position, WindState, load_config, save_config
from wind import WindSolution, calculate_wind_solution

MILS_PER_DEGREE = 6400.0 / 360.0


def distance(a: Position, b: Position) -> float:
    """두 지도 위치 사이의 수평 거리를 반환합니다."""
    return math.hypot(b.easting - a.easting, b.northing - a.northing)


def azimuth_degrees(a: Position, b: Position) -> float:
    """위치 a에서 b까지의 격자 방향각을 도 단위로 반환합니다."""
    dx = b.easting - a.easting
    dy = b.northing - a.northing
    return math.degrees(math.atan2(dx, dy)) % 360.0


def target_from_fo(
    fo: Position,
    direction: float,
    range_m: float,
    elevation: float,
) -> Position:
    """관측자의 극좌표 관측값으로 목표 좌표를 계산합니다."""
    radians = math.radians(direction)
    return Position(
        easting=fo.easting + math.sin(radians) * range_m,
        northing=fo.northing + math.cos(radians) * range_m,
        elevation=elevation,
    )


def prompt_float(label: str, default: float) -> float:
    """빈 입력 시 기본값을 유지하면서 실수를 입력받습니다."""
    value = input(f"{label} [{default:.1f}]: ").strip()
    return default if not value else float(value)


def prompt_position(title: str, current: Position) -> Position:
    """3차원 위치를 입력받습니다."""
    print(f"\n{title}")
    return Position(
        easting=prompt_float("  동향 좌표", current.easting),
        northing=prompt_float("  북향 좌표", current.northing),
        elevation=prompt_float("  고도", current.elevation),
    )


def prompt_wind(current: WindState) -> WindState:
    """풍속과 풍향을 입력받습니다."""
    print("\n바람 (바람이 불어오는 방향)")
    return WindState(
        speed=prompt_float("  풍속 m/s", current.speed),
        direction=prompt_float("  풍향 도", current.direction) % 360.0,
    )


def print_header(config: AppConfig) -> None:
    """애플리케이션 제목과 현재 저장된 상태를 출력합니다."""
    print("=" * 60)
    print("ARMA REFORGER M252 / M821 사격 통제 시스템")
    print("=" * 60)
    print(f"박격포: {format_position(config.mortar)}")
    print(f"관측자: {format_position(config.fo)}")
    print(f"바람:   {config.wind.direction:.0f}° @ {config.wind.speed:.1f} m/s")
    print("=" * 60)


def format_position(position: Position) -> str:
    """터미널 표시용 위치 문자열을 구성합니다."""
    return (
        f"동 {position.easting:.1f} "
        f"북 {position.northing:.1f} "
        f"고도 {position.elevation:.1f}"
    )


def print_solution(
    target: Position,
    range_m: float,
    elevation_difference: float,
    azimuth: float,
    solutions: list[tuple[FiringSolution, WindSolution]],
) -> None:
    """목표 기하 정보와 장약별 사격 제원을 표시합니다."""
    print("\n" + "=" * 60)
    print(f"목표:        {format_position(target)}")
    print(f"거리:        {range_m:.1f} m")
    print(f"고도차:      {elevation_difference:+.1f} m")
    print(f"방향각:      {azimuth:.1f}° / {azimuth * MILS_PER_DEGREE:.0f} mil")
    print("=" * 60)
    for solution, wind in solutions:
        corrected_azimuth = (
            azimuth * MILS_PER_DEGREE + wind.azimuth_correction
        ) % 6400.0
        _print_charge_solution(solution, wind, corrected_azimuth)


def _print_charge_solution(
    solution: FiringSolution,
    wind: WindSolution,
    corrected_azimuth: float,
) -> None:
    print(f"장약 {solution.charge}")
    print(f"  사각:              {solution.elevation_mil:.1f} mil")
    print(f"  보정 사각:         {solution.corrected_elevation_mil:.1f} mil")
    print(f"  보정 방향각:       {corrected_azimuth:.0f} mil")
    print(f"  비행시간:          {solution.flight_time:.1f} s")
    print(f"  분산:              ±{solution.dispersion:.1f} m")
    print(f"  횡풍/역풍:         {wind.crosswind:+.1f} / {wind.headwind:+.1f} m/s")
    print(
        f"  풍향 보정:         방향각 {wind.azimuth_correction:+.1f} mil, "
        f"거리 {wind.range_correction:+.1f} m"
    )


def run_once(config: AppConfig) -> AppConfig:
    """하나의 사격 임무를 입력받고 모든 유효한 제원을 표시합니다."""
    mortar = prompt_position("박격포", config.mortar)
    fo = prompt_position("관측자", config.fo)
    wind = prompt_wind(config.wind)
    print("\n관측자 기준 목표")
    target_direction = prompt_float("  방향각 도", 0.0) % 360.0
    target_distance = prompt_float("  거리 m", 500.0)
    target_elevation = prompt_float("  목표 고도", fo.elevation)
    target = target_from_fo(fo, target_direction, target_distance, target_elevation)
    updated = replace(config, mortar=mortar, fo=fo, wind=wind)
    return _calculate_and_display(updated, target)


def _calculate_and_display(config: AppConfig, target: Position) -> AppConfig:
    tables = load_ballistic_data()
    range_m = distance(config.mortar, target)
    elevation_difference = target.elevation - config.mortar.elevation
    azimuth = azimuth_degrees(config.mortar, target)
    ballistic_solutions = get_all_firing_solutions(
        range_m, elevation_difference, tables
    )
    combined = [
        (
            solution,
            calculate_wind_solution(
                config.wind.speed,
                config.wind.direction,
                azimuth,
                range_m,
                solution.flight_time,
            ),
        )
        for solution in ballistic_solutions
    ]
    print_solution(target, range_m, elevation_difference, azimuth, combined)
    return config


def main() -> None:
    """대화형 계산기 루프를 실행합니다."""
    config = load_config()
    while True:
        print_header(config)
        config = run_once(config)
        save_config(config)
        if input("다른 목표를 계산하시겠습니까? [Y/n]: ").strip().lower() == "n":
            break


if __name__ == "__main__":
    main()
