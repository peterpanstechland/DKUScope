# Python Control Station & Detection Server

## Quick Start (development)

```bash
cd software/python
pip install -r requirements.txt
python main.py
```

Inside the UI: configure, calibrate, **Start Detection** → `ws://localhost:8765` for TouchDesigner.

## Build Windows executable (PyInstaller)

```powershell
cd software/python
.\build.ps1
```

Output:
- `dist/DKUScope/DKUScope.exe` — run this on the target PC (no Python install needed)
- `dist/DKUScope.zip` — zip of the full folder

Config is read/written from `config/project_config.json` **next to the exe**. On first run, a default config is copied if missing.

### CI / GitHub Release

| Workflow | Trigger | Result |
|----------|---------|--------|
| **Build** | Push/PR changing `software/python/**` | Uploads `DKUScope.zip` artifact (14 days) |
| **Release** | Push tag `v*` (e.g. `v0.1.0`) | GitHub Release with `DKUScope-v0.1.0-windows.zip` |

Create a release locally:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Or: GitHub → Actions → **Release** → Run workflow → enter tag `v0.1.0`.

Target machine still needs **TouchDesigner** separately; this bundle is the Python control station only.

## Optional Headless Scripts

```bash
python scripts/run_detection_server.py
python scripts/run_projection_calibration.py
python scripts/camera_grid_probe.py
```

## Folder Structure

- `main.py` - Control station entry point
- `control_station/` - UI, calibration, detection, WebSocket modules
- `scripts/` - Standalone runnable scripts
- `config/` - JSON configuration files
