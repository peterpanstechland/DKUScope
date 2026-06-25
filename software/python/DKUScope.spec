# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DKUScope Control Station (Windows onedir build)
#
# Local build:
#   cd software/python
#   pip install -r requirements-build.txt
#   pyinstaller DKUScope.spec --noconfirm

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH)

cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all("cv2")
pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")

hiddenimports = [
    "control_station",
    "control_station.ui",
    "control_station.paths",
    "control_station.config_manager",
    "control_station.config_schema",
    "control_station.detection_service",
    "control_station.detection_runner",
    "control_station.detection_monitor",
    "control_station.ws_server",
    "control_station.camera_service",
    "control_station.camera_preview",
    "control_station.camera_calibration_tab",
    "control_station.ota_service",
    "control_station.calibration_service",
    "control_station.projection_calibration_service",
    "control_station.color_pick_service",
    "control_station.i18n",
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    "websockets.legacy.client",
    "asyncio",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
] + cv2_hiddenimports + pil_hiddenimports

datas = [
    (str(root / "config" / "project_config.json"), "config"),
] + cv2_datas + pil_datas

binaries = cv2_binaries + pil_binaries

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DKUScope",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DKUScope",
)
