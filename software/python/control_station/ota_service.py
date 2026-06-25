from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .paths import get_install_dir
from .log_service import get_logger

GITHUB_REPO = "peterpanstechland/DKUScope"
USER_AGENT = f"DKUScope-Updater/{__version__}"
ota_logger = get_logger("ota")
WINDOWS_ZIP_PATTERN = re.compile(r"DKUScope-v.+?-windows\.zip$", re.IGNORECASE)


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    download_url: str
    asset_name: str
    body: str
    size: int


@dataclass
class UpdateCheckResult:
    current_version: str
    latest: Optional[ReleaseInfo]
    update_available: bool
    error: str = ""


def parse_version(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lstrip("vV")
    parts: list[int] = []
    for piece in cleaned.split("."):
        if not piece:
            continue
        digits = re.match(r"(\d+)", piece)
        parts.append(int(digits.group(1)) if digits else 0)
    return tuple(parts) if parts else (0,)


def get_current_version() -> str:
    return __version__


def is_update_available(current: str, latest: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _github_get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _latest_from_release_redirect() -> Optional[ReleaseInfo]:
    """Fallback when GitHub API is rate-limited: follow /releases/latest redirect."""
    req = urllib.request.Request(
        f"https://github.com/{GITHUB_REPO}/releases/latest",
        method="HEAD",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        final_url = resp.geturl()
    tag = final_url.rstrip("/").split("/")[-1]
    if not tag.startswith("v"):
        return None
    return ReleaseInfo(
        version=tag.lstrip("vV"),
        tag=tag,
        download_url=(
            f"https://github.com/{GITHUB_REPO}/releases/download/"
            f"{tag}/DKUScope-{tag}-windows.zip"
        ),
        asset_name=f"DKUScope-{tag}-windows.zip",
        body="",
        size=0,
    )


def check_for_update() -> UpdateCheckResult:
    current = get_current_version()
    latest: Optional[ReleaseInfo] = None
    api_error = ""

    try:
        data = _github_get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
        tag = str(data.get("tag_name", ""))
        version = tag.lstrip("vV")
        body = str(data.get("body") or "").strip()
        assets = data.get("assets") or []

        download_url = ""
        asset_name = ""
        size = 0
        for asset in assets:
            name = str(asset.get("name", ""))
            if WINDOWS_ZIP_PATTERN.search(name):
                download_url = str(asset.get("browser_download_url", ""))
                asset_name = name
                size = int(asset.get("size") or 0)
                break

        if download_url:
            latest = ReleaseInfo(
                version=version,
                tag=tag,
                download_url=download_url,
                asset_name=asset_name,
                body=body,
                size=size,
            )
    except urllib.error.HTTPError as exc:
        api_error = f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        api_error = str(exc.reason)
    except Exception as exc:
        api_error = str(exc)

    if latest is None:
        try:
            latest = _latest_from_release_redirect()
        except Exception as exc:
            return UpdateCheckResult(current, None, False, error=api_error or str(exc))

    if latest is None:
        return UpdateCheckResult(current, None, False, error=api_error or "No release found")

    return UpdateCheckResult(
        current_version=current,
        latest=latest,
        update_available=is_update_available(current, latest.version),
    )


def download_release(
    release: ReleaseInfo,
    dest_dir: Path,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / release.asset_name

    req = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length") or release.size or 0)
        downloaded = 0
        chunk_size = 256 * 1024
        with zip_path.open("wb") as out:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

    return zip_path


def extract_release_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    for candidate in (dest_dir / "DKUScope", dest_dir):
        exe = candidate / "DKUScope.exe"
        if exe.exists():
            return candidate

    raise FileNotFoundError("DKUScope.exe not found in release archive")


def can_apply_update() -> bool:
    return bool(getattr(sys, "frozen", False))


def apply_update(staged_root: Path) -> None:
    if not can_apply_update():
        raise RuntimeError("OTA install is only supported for the packaged Windows app")

    install_dir = get_install_dir()
    exe_path = install_dir / "DKUScope.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Current install not found: {exe_path}")

    updater_dir = Path(tempfile.gettempdir()) / "dkuscope-update"
    updater_dir.mkdir(parents=True, exist_ok=True)
    updater_script = updater_dir / "apply_update.bat"

    script = f"""@echo off
setlocal EnableExtensions
set "PID={os.getpid()}"
set "SRC={staged_root}"
set "DST={install_dir}"
set "EXE={exe_path}"

:wait_loop
tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL
if %ERRORLEVEL%==0 (
  timeout /t 1 /nobreak >NUL
  goto wait_loop
)

if exist "%DST%\\config" (
  robocopy "%SRC%" "%DST%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP /XD config >NUL
) else (
  robocopy "%SRC%" "%DST%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >NUL
)
if %ERRORLEVEL% GEQ 8 exit /b %ERRORLEVEL%

start "" "%EXE%"
del "%~f0"
"""
    updater_script.write_text(script, encoding="ascii")

    subprocess.Popen(
        ["cmd.exe", "/c", str(updater_script)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def open_release_page(tag: str) -> None:
    url = f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}"
    os.startfile(url)  # type: ignore[attr-defined]


def format_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "?"
    mb = num_bytes / (1024 * 1024)
    return f"{mb:.1f} MB"


class UpdateWorker:
    """Run check/download in a background thread."""

    def __init__(
        self,
        on_check_done: Callable[[UpdateCheckResult], None],
        on_download_progress: Optional[Callable[[int, int], None]] = None,
        on_download_done: Optional[Callable[[Path, Optional[Exception]], None]] = None,
    ) -> None:
        self._on_check_done = on_check_done
        self._on_download_progress = on_download_progress
        self._on_download_done = on_download_done
        self._thread: Optional[threading.Thread] = None
        self.work_dir = Path(tempfile.gettempdir()) / "dkuscope-update" / "work"

    def check_async(self) -> None:
        self._thread = threading.Thread(target=self._check, daemon=True)
        self._thread.start()

    def download_async(self, release: ReleaseInfo) -> None:
        self._thread = threading.Thread(
            target=self._download,
            args=(release,),
            daemon=True,
        )
        self._thread.start()

    def _check(self) -> None:
        result = check_for_update()
        self._on_check_done(result)

    def _download(self, release: ReleaseInfo) -> None:
        err: Optional[Exception] = None
        staged_root: Optional[Path] = None
        try:
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir, ignore_errors=True)
            self.work_dir.mkdir(parents=True, exist_ok=True)
            zip_path = download_release(
                release,
                self.work_dir,
                on_progress=self._on_download_progress,
            )
            extract_dir = self.work_dir / "extracted"
            staged_root = extract_release_zip(zip_path, extract_dir)
        except Exception as exc:
            err = exc
        if self._on_download_done:
            self._on_download_done(staged_root, err)
