# Bottom-Camera Color Detection Pipeline

## Objective

Detect base color changes for each grid cell in real time from a bottom-facing camera.

## Input Assumptions

- Camera is globally shuttered and fixed.
- Grid is known and calibrated.
- Base colors map to semantic classes (building type, road, water, etc.).

## Pipeline Stages

1. Frame acquisition  
   Read frame with fixed manual camera parameters.

2. Geometric rectification  
   Use homography to map image to canonical grid plane.

3. Cell ROI extraction  
   For each cell, sample an inner ROI (avoid edge bleed).

4. Color feature extraction  
   Convert ROI to Lab color space and use median values.

5. Classification  
   Compare to configured class centroids in Lab space.

6. Confidence gate  
   If distance exceeds threshold, mark as `unknown`.

7. Temporal smoothing  
   Majority vote across last 3-5 frames per cell.

8. Event generation  
   Emit event only when stable class changes.

## Why Lab Instead of RGB

- Better separation under moderate illumination variation.
- More robust for difficult pairs like black/brown and pink/white.

## Stability Controls

- Lock exposure, gain, and white balance.
- Keep constant illumination.
- Use per-session color calibration cards.
- Store calibration in `config/colors.yaml`.

## Suggested Per-Cell Output

```json
{
  "cell_id": "r03_c07",
  "class_id": 5,
  "label": "dormitory",
  "confidence": 0.91,
  "timestamp_ms": 1710000000000
}
```

## Practical Notes for 640x480

- Start with smaller grids to validate robustness.
- Keep enough pixels per cell after rectification.
- Avoid pushing large grid density before calibration is stable.

