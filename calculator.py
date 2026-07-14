"""Professional console UI for an Arma Reforger M252 fire control system."""

from __future__ import annotations

import math
from dataclasses import replace

from ballistics import FiringSolution, get_all_firing_solutions, load_ballistic_data
from config import AppConfig, Position, WindState, load_config, save_config
from wind import WindSolution, calculate_wind_solution

MILS_PER_DEGREE = 6400.0 / 360.0


def distance(a: Position, b: Position) -> float:
    """Return horizontal distance between two map positions."""
    return math.hypot(b.easting - a.easting, b.northing - a.northing)


def azimuth_degrees(a: Position, b: Position) -> float:
    """Return grid azimuth in degrees from position a to b."""
    dx = b.easting - a.easting
    dy = b.northing - a.northing
    return math.degrees(math.atan2(dx, dy)) % 360.0


def target_from_fo(
    fo: Position,
    direction: float,
    range_m: float,
    elevation: float,
) -> Position:
    """Calculate target coordinates from FO polar observation."""
    radians = math.radians(direction)
    return Position(
        easting=fo.easting + math.sin(radians) * range_m,
        northing=fo.northing + math.cos(radians) * range_m,
        elevation=elevation,
    )


def prompt_float(label: str, default: float) -> float:
    """Prompt for a float while preserving defaults on blank input."""
    value = input(f"{label} [{default:.1f}]: ").strip()
    return default if not value else float(value)


def prompt_position(title: str, current: Position) -> Position:
    """Prompt for a three-dimensional position."""
    print(f"\n{title}")
    return Position(
        easting=prompt_float("  Easting", current.easting),
        northing=prompt_float("  Northing", current.northing),
        elevation=prompt_float("  Elevation", current.elevation),
    )


def prompt_wind(current: WindState) -> WindState:
    """Prompt for wind speed and direction."""
    print("\nWind (direction FROM which wind blows)")
    return WindState(
        speed=prompt_float("  Speed m/s", current.speed),
        direction=prompt_float("  Direction degrees", current.direction) % 360.0,
    )


def print_header(config: AppConfig) -> None:
    """Print application title and current persisted context."""
    print("=" * 60)
    print("ARMA REFORGER M252 / M821 FIRE CONTROL SYSTEM")
    print("=" * 60)
    print(f"Mortar: {format_position(config.mortar)}")
    print(f"FO:     {format_position(config.fo)}")
    print(f"Wind:   {config.wind.direction:.0f}° @ {config.wind.speed:.1f} m/s")
    print("=" * 60)


def format_position(position: Position) -> str:
    """Format a position for terminal display."""
    return (
        f"E {position.easting:.1f} "
        f"N {position.northing:.1f} "
        f"ALT {position.elevation:.1f}"
    )


def print_solution(
    target: Position,
    range_m: float,
    elevation_difference: float,
    azimuth: float,
    solutions: list[tuple[FiringSolution, WindSolution]],
) -> None:
    """Render target geometry and charge solutions."""
    print("\n" + "=" * 60)
    print(f"Target:      {format_position(target)}")
    print(f"Distance:    {range_m:.1f} m")
    print(f"Elevation Δ: {elevation_difference:+.1f} m")
    print(f"Direction:   {azimuth:.1f}° / {azimuth * MILS_PER_DEGREE:.0f} mil")
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
    print(f"Charge {solution.charge}")
    print(f"  Elevation:          {solution.elevation_mil:.1f} mil")
    print(f"  Corrected Elev:     {solution.corrected_elevation_mil:.1f} mil")
    print(f"  Corrected Azimuth:  {corrected_azimuth:.0f} mil")
    print(f"  TOF:                {solution.flight_time:.1f} s")
    print(f"  Dispersion:         ±{solution.dispersion:.1f} m")
    print(f"  Cross/Head Wind:    {wind.crosswind:+.1f} / {wind.headwind:+.1f} m/s")
    print(
        f"  Wind Correction:    Az {wind.azimuth_correction:+.1f} mil, "
        f"Rg {wind.range_correction:+.1f} m"
    )


def run_once(config: AppConfig) -> AppConfig:
    """Collect one mission and display every valid solution."""
    mortar = prompt_position("Mortar", config.mortar)
    fo = prompt_position("FO", config.fo)
    wind = prompt_wind(config.wind)
    print("\nTarget from FO")
    target_direction = prompt_float("  Direction degrees", 0.0) % 360.0
    target_distance = prompt_float("  Distance m", 500.0)
    target_elevation = prompt_float("  Target elevation", fo.elevation)
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
    """Run the interactive calculator loop."""
    config = load_config()
    while True:
        print_header(config)
        config = run_once(config)
        save_config(config)
        if input("Another target? [Y/n]: ").strip().lower() == "n":
            break


if __name__ == "__main__":
    main()
