# Hardware Specification

## Physical Context

- Camera is mounted under the table and looks upward to the block bases.
- Grid uses Lego-compatible unit logic.
- Projection is mounted above table.

## Table Layer Stack (Top to Bottom)

1. Interaction layer (blocks on grid)
2. Grid constraint layer (cut template or pockets)
3. Transparent plate (acrylic)
4. Light control cavity (black interior walls)
5. Bottom camera + illumination assembly

## Camera Requirements

- Global shutter (already selected)
- Current resolution: 640x480 (usable for MVP)
- Stable fixed mount (no motion after calibration)
- Prefer manual controls:
  - exposure locked
  - white balance locked
  - gain locked

## Lighting Requirements

- Even neutral light under table (around 5000K)
- Avoid directional hotspots
- Matte black shielding to reduce reflections

## Grid Sizing Formulas

Let:

- `s` = block base edge length (cm)
- `g` = gap between cells (cm)
- `N` = number of cells per side

Effective active area:

`L = N*s + (N-1)*g`

Outer table size with border `b` on each side:

`L_out = L + 2*b`

## Example: 6x6 Unit Logic

Given:

- `s = 4.8 cm`
- optional gap `g = 2.4 cm` (half-unit road)

Then:

- `N=8` -> active area `55.2 cm`
- `N=16` -> active area `112.8 cm`

## Mechanical Tolerance Recommendations

- Cell fixture tolerance: +0.3 to +0.6 mm
- Keep removable top frame for maintenance
- Add cable channels and ventilation under table

## Upgrade Path

1. MVP with single camera and single projector
2. Better camera resolution and optics
3. Multi-camera and multi-projector stitching if needed

