# DKUScope Tangible Planning Table

A tangible interactive table for collaborative campus planning, inspired by MIT CityScope / Bits-and-Bricks.

Users place colored Lego blocks on a physical grid table. A bottom-mounted camera detects block colors in real time, classifies building types, and drives a projection mapping overlay on the table surface.

## Repository Structure

```
DKUScope/
│
├── docs/                          # Technical documentation
│   ├── architecture.md            # System design & data flow
│   ├── hardware-spec.md           # Table sizing & camera specs
│   ├── color-detection-pipeline.md
│   ├── data-model-and-rules.md
│   ├── integration-protocol.md    # WebSocket JSON contract
│   ├── projection-mapping-touchdesigner.md
│   └── development-plan.md
│
├── software/
│   ├── python/                    # Control station & detection server
│   │   ├── main.py                # Launch control station UI
│   │   ├── requirements.txt
│   │   ├── config/                # JSON configuration
│   │   ├── control_station/       # All Python modules
│   │   └── scripts/               # Standalone scripts
│   └── touchdesigner/             # TD projection mapping projects
│
├── hardware/
│   ├── bom/                       # Bill of materials
│   ├── photos/                    # Build & setup photos
│   └── table_design/              # Engineering drawings
│
└── design/
    ├── 3d_models/                 # 3D printable parts (.stl, .step)
    └── laser_cut/                 # Laser cutting files (.dxf, .svg)
```

## Quick Start

```bash
cd software/python
pip install -r requirements.txt

# 1. Configure and calibrate
python main.py

# 2. Run detection + WebSocket server
python scripts/run_detection_server.py

# 3. In TouchDesigner, connect WebSocket DAT to ws://localhost:8765
```

## Features

- **Bilingual UI** (zh_CN / en_US) with real-time camera preview
- **Bottom camera calibration** (4-point perspective warp)
- **Projection calibration** (chessboard + top camera auto-detect)
- **Camera-based color sampling** for building class definition
- **Multi-table layout** (2x2, 1x3, etc.) with per-unit calibration
- **Real-time detection** with WebSocket broadcast to TouchDesigner
- **Configurable building rules**: single-cell, multi-cell, and fixed large units

## For Collaborators

| You work on... | Go to... |
|----------------|----------|
| Python code | `software/python/` |
| TouchDesigner | `software/touchdesigner/` |
| Table building | `hardware/` |
| 3D printing / laser cutting | `design/` |
| Project docs | `docs/` |

## References

- [GUI3D](https://github.com/irawinder/GUI3D)
- [MIT CityScope](https://www.media.mit.edu/projects/cityscope/overview/)
- [Lego Logistics](https://ira.mit.edu/blog/lego-logistics)
