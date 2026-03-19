# DKUScope Tangible Planning Table

This repository contains planning and implementation docs for a tangible interactive table project inspired by CityScope/Bits-and-Bricks workflows.

The system goal:

- Use a bottom-mounted global shutter camera to detect block base colors on a grid.
- Reconstruct grid occupancy and building semantics in real time.
- Drive projector visuals with projection mapping on the physical table.

## Current Scope

This repo currently focuses on documentation-first delivery:

- Hardware specification and sizing
- Software architecture and modules
- Color detection pipeline for bottom camera setup
- Projection mapping workflow (TouchDesigner focused)
- Data model for single-cell, multi-cell, and fixed large units
- BOM and staged implementation plan

## Documentation Map

See `docs/README.md` for the full document index.

## Recommended Baseline

- Camera: global shutter, currently 640x480 (MVP compatible)
- Block base: 6x6 or 8x8 plate strategy (documented trade-offs)
- Grid baseline: start from 8x8 or 16x16 only after calibration is stable
- Mapping tool: TouchDesigner (fast iteration) or Unity (heavier engineering)

## Implemented in This Repo

- Python control station UI (`tkinter`) for:
  - camera selection with live preview (fixed right panel)
  - four-point calibration wizard
  - camera-based color sampling per building class
  - block/plate size, grid, and multi-table layout config
  - building type to color mapping (editable table)
- Real-time detection server:
  - reads camera, applies perspective warp, classifies per-cell color
  - broadcasts grid state over WebSocket (for TouchDesigner)
- JSON config persistence:
  - default path: `config/project_config.json`

## Quick Start

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start control station (configure camera, calibrate, sample colors):
   - `python main.py`
3. Start detection + WebSocket server:
   - `python scripts/run_detection_server.py`
4. In TouchDesigner, add a `WebSocket DAT` and connect to:
   - `ws://localhost:8765`
5. Optional standalone camera probe:
   - `python scripts/camera_grid_probe.py --config config/project_config.json`

## References

- [GUI3D repository](https://github.com/irawinder/GUI3D)
- [MIT CityScope overview](https://www.media.mit.edu/projects/cityscope/overview/)
- [Lego Logistics article](https://ira.mit.edu/blog/lego-logistics)

