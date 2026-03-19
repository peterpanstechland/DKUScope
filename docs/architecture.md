# System Architecture

## Goal

Build a real-time tangible planning table where physical block placement changes are detected from below and projected back onto the table surface with low latency.

## Design Principles

- Keep module responsibilities clear.
- Avoid hardcoded thresholds and geometry in code.
- Reuse shared functions and data contracts.
- Make calibration and mapping config-driven.

## High-Level Modules

1. `vision`  
   Reads camera frames, rectifies perspective, extracts per-cell color observations.

2. `reconstruction`  
   Converts per-cell colors into occupancy states and merges connected cells into buildings.

3. `simulation`  
   Computes metrics from current world state (coverage, density, path, score, etc.).

4. `rendering`  
   Produces visual layers for projection and optional side display.

5. `orchestration/io`  
   Handles transport (WebSocket/UDP), timing, logging, and health checks.

## Runtime Data Flow

1. Camera frame acquired from bottom view.
2. Perspective correction to canonical grid plane.
3. Per-cell color classification with confidence.
4. Temporal smoothing and event extraction (cell changed).
5. Connected-component merge into building entities.
6. Simulation recompute for changed region or full grid.
7. Render payload sent to projection engine.
8. Projection output mapped to physical scene.

## Latency Budget (Target)

- Capture + preprocess: 15-30 ms
- Classification + smoothing: 10-20 ms
- Reconstruction + simulation: 10-30 ms
- Render + output transport: 15-30 ms
- Projection/display response: 20-40 ms

Expected total: 70-150 ms.

## Repository Layout

```text
DKUScope/
  README.md
  docs/                           # Technical documents
  software/
    python/                       # Control station + detection server
      main.py
      requirements.txt
      config/project_config.json
      control_station/            # All Python modules
      scripts/                    # Standalone scripts
    touchdesigner/                # TD project files (.toe)
  hardware/
    bom/                          # Bill of materials
    photos/                       # Build photos
    table_design/                 # Engineering drawings
  design/
    3d_models/                    # 3D print files (.stl, .step)
    laser_cut/                    # Laser cut files (.dxf, .svg)
```

## Configuration First

Keep these outside code:

- Grid dimension, cell size, spacing
- Color centers and confidence thresholds
- Fixed building footprints
- Camera intrinsics/extrinsics
- Projector warp parameters

## Recommended Stack

- Python + OpenCV for camera and classification
- Python WebSocket service for state/events
- TouchDesigner for projection mapping and visual composition

