from __future__ import annotations

import shutil
import sys
from pathlib import Path


def get_install_dir() -> Path:
    """Directory for writable files (config). Dev: software/python; frozen: exe folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundled_path(relative: str) -> Path:
    """Read-only bundled resource path."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative  # type: ignore[attr-defined]
    return get_install_dir() / relative


def get_default_config_path() -> Path:
    return get_install_dir() / "config" / "project_config.json"


def get_logs_dir() -> Path:
    return get_install_dir() / "logs"


def ensure_default_config() -> Path:
    """Copy bundled default config next to the install dir if missing."""
    target = get_default_config_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        bundled = get_bundled_path("config/project_config.json")
        if bundled.exists():
            shutil.copy2(bundled, target)
    return target
