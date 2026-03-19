# TouchDesigner Projects

This folder contains TouchDesigner (.toe) project files for projection mapping and visualization.

## What Goes Here

- `mapping.toe` - Main projection mapping project
- Any custom GLSL shaders or Python extensions used inside TD
- Exported presets and mapping profiles

## How It Connects

The TD project receives real-time grid state from the Python detection server via WebSocket:

```
ws://localhost:8765
```

Use a `WebSocket DAT` to connect, then parse the JSON with a `JSON DAT` or `Script DAT`.

## Warp Matrix

If projection calibration has been done, the warp matrix is stored in:

```
software/python/config/project_config.json → projection.warp_matrix
```

Use this 3x3 matrix to pre-distort output before sending to the projector.
