# MortarCalculator

Professional Arma Reforger mortar fire-control calculator for the official **M252 Mortar** firing **M821 HE** with charges **0-4**.

## Features

- M252/M821 charge recommendations from JSON ballistic tables.
- Linear interpolation with `scipy.interpolate.interp1d` for range, elevation, time of flight, correction, and dispersion.
- Target coordinate calculation from forward-observer direction and distance.
- Elevation-difference correction for targets above or below the mortar.
- Wind component model using wind direction, shot azimuth, range, and projectile flight time.
- Automatic azimuth and elevation corrections.
- Persistent startup defaults for mortar, FO, wind, and settings in `config.json`.
- Terminal UI designed for field-style fire missions.

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Requirements

- Python 3.12
- numpy
- scipy

## Usage

Run the calculator from the repository root:

```bash
python calculator.py
```

The program prompts for:

1. Mortar position: easting, northing, elevation.
2. FO position: easting, northing, elevation.
3. Wind speed in meters per second.
4. Wind direction in degrees **from which** the wind blows.
5. Target direction and distance from the FO.
6. Target elevation.

Blank input accepts the displayed default. The latest mortar, FO, and wind entries are saved to `config.json` after every fire mission.

## Wind Correction

Wind is decomposed relative to the mortar-to-target azimuth:

- Crosswind estimates lateral drift and converts it to a mil azimuth correction.
- Headwind/tailwind estimates a range correction.
- Projectile time of flight is part of the calculation, so slower high-angle shots receive stronger wind effects than faster shots.

The model intentionally avoids fixed per-charge constants in the UI. Corrections are generated from wind vector geometry, range, and interpolated time of flight.

## Ballistic Model

Ballistic data lives in `data/m821.json`. Each charge table stores:

- `range`
- `mil`
- `time`
- `elevation_correction`
- `dispersion`

`ballistics.py` loads these tables and builds `scipy.interpolate.interp1d` interpolators. The calculator recommends every charge whose table brackets the requested mortar-to-target range and displays all valid firing solutions.

## Project Structure

```text
MortarCalculator/
├── calculator.py
├── ballistics.py
├── wind.py
├── config.py
├── data/
│   └── m821.json
├── config.json
├── README.md
└── requirements.txt
```

## Future Roadmap

- Add verified live-fire calibration data for each Arma Reforger game update.
- Add optional metric grid parsing helpers for common player coordinate formats.
- Add non-interactive CLI flags for scripted fire missions.
- Add unit tests for wind signs, interpolation boundaries, and config migration.
- Add saved target history and mission export.
