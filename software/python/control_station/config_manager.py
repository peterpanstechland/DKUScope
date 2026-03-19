from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .config_schema import ProjectConfig


DEFAULT_CONFIG_PATH = Path("config/project_config.json")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_config(path: Optional[Path] = None) -> ProjectConfig:
    resolved = path or DEFAULT_CONFIG_PATH
    if not resolved.exists():
        return ProjectConfig()
    with resolved.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return ProjectConfig.from_dict(raw)


def save_config(config: ProjectConfig, path: Optional[Path] = None) -> Path:
    resolved = path or DEFAULT_CONFIG_PATH
    ensure_parent(resolved)
    with resolved.open("w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
    return resolved

