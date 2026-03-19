# Python Control Station & Detection Server

## Quick Start

```bash
cd software/python
pip install -r requirements.txt

# Launch control station UI
python main.py

# Run detection + WebSocket server
python scripts/run_detection_server.py

# Run projection calibration
python scripts/run_projection_calibration.py
```

## Folder Structure

- `main.py` - Control station entry point
- `control_station/` - UI, calibration, detection, WebSocket modules
- `scripts/` - Standalone runnable scripts
- `config/` - JSON configuration files
