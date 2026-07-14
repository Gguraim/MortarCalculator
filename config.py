"""박격포 사격 통제 시스템의 영구 설정."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("config.json")


@dataclass(slots=True)
class Position:
    """미터 단위의 게임 지도 위치."""

    easting: float = 0.0
    northing: float = 0.0
    elevation: float = 0.0


@dataclass(slots=True)
class WindState:
    """풍속과 바람이 불어오는 방향."""

    speed: float = 0.0
    direction: float = 0.0


@dataclass(slots=True)
class Settings:
    """사용자가 조정할 수 있는 애플리케이션 설정."""

    ammo: str = "M821 HE"
    weapon: str = "M252 Mortar"


@dataclass(slots=True)
class AppConfig:
    """저장되는 계산기 상태 전체."""

    mortar: Position = field(default_factory=Position)
    fo: Position = field(default_factory=Position)
    wind: WindState = field(default_factory=WindState)
    settings: Settings = field(default_factory=Settings)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    return data.get(name, {}) if isinstance(data.get(name, {}), dict) else {}


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """애플리케이션 상태를 불러오며, 설정이 없으면 기본값을 반환합니다."""
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
    """애플리케이션 상태를 서식 있는 JSON으로 저장합니다."""
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
