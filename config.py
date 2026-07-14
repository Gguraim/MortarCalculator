"""Persistent configuration for the mortar fire control system."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("config.json")


@dataclass(slots=True)
class Position:
    """A game-map position in meters."""

    easting: float = 0.0
    northing: float = 0.0
    elevation: float = 0.0


@dataclass(slots=True)
class WindState:
    """Wind speed and direction from which the wind blows."""

    speed: float = 0.0
    direction: float = 0.0


@dataclass(slots=True)
class Settings:
    """User-adjustable application settings."""

    ammo: str = "M821 HE"
    weapon: str = "M252 Mortar"


@dataclass(slots=True)
class AppConfig:
    """Complete persisted calculator state."""

    mortar: Position = field(default_factory=Position)
    fo: Position = field(default_factory=Position)
    wind: WindState = field(default_factory=WindState)
    settings: Settings = field(default_factory=Settings)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    return data.get(name, {}) if isinstance(data.get(name, {}), dict) else {}


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """Load application state, returning defaults when no config exists."""
    if not path.exists():
        return AppConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(
        mortar=Position(**_section(data, "mortar")),
        fo=Position(**_section(data, "fo")),
        wind=WindState(**_section(data, "wind")),
        settings=Settings(**_section(data, "settings")),
    )


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    """Persist application state as formatted JSON."""
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
