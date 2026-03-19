# Projection Mapping with TouchDesigner

## Why TouchDesigner

- Fast visual iteration
- Native mapping operators
- Good real-time pipeline control
- Easy integration from WebSocket/OSC/UDP

## Core Mapping Concept

Projection mapping aligns digital render output to physical geometry on the table.

In this project:

- Input state comes from camera-driven grid detection.
- Visuals are generated per grid/building/metric.
- Final image is warped to match physical table and block positions.

## Recommended TouchDesigner Network Blocks

1. **Input**
   - `websocketDAT` or `udpInDAT` for state stream
   - parse JSON into channels/tables

2. **State Processing**
   - Convert cell/building state into texture maps
   - Optional smoothing and transitions

3. **Render**
   - TOP/COMP network to draw roads, highlights, heatmaps, labels
   - Layered compositing for class colors + analytics overlays

4. **Mapping/Warp**
   - `kantanMapper` (or native warp pipeline)
   - Define projector output surface and correction points
   - Store mapping profile for reuse

5. **Output**
   - Fullscreen projector output
   - Optional debug monitor output

## Calibration Workflow

1. Show grid calibration pattern via projector.
2. Align projected corners to physical table corners.
3. Align internal reference points (center and edge checkpoints).
4. Save mapping profile.
5. Validate by projecting per-cell boundaries and checking physical alignment.

## Multi-Layer Visual Strategy

- Base layer: roads/land-use context
- Occupancy layer: per-cell class color
- Entity layer: building footprint borders and selection
- Analysis layer: heatmap, warnings, score text

## Interaction Hooks

- Highlight changed cells on `cell_event`
- Animate merge/split for multi-cell buildings
- Use confidence-driven visual cues when classification is uncertain

## Operational Notes

- Lock projector position physically.
- Recalibrate if camera, table, or projector moves.
- Version mapping files together with config snapshots.

