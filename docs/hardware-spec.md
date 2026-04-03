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

- `s` = nominal cell pocket / block base edge (cm). Use **~4.9 cm** so the physical pocket is slightly larger than the classic 6-stud pitch (4.8 cm) and leaves **assembly and cutting tolerance** without binding.
- `g` = full **road** width between adjacent cell centers’ boundaries — i.e. gap **between** cells (cm).
- `N` = number of cells per side.
- `b` = margin from the **outer aperture** (`L_out`) to the first/last cell (cm), **on each side**.

Effective active area (only the grid, edge to edge of the cell array):

`L = N*s + (N-1)*g`

### Modular edge convention (half-road border)

For multi-table alignment, set the physical border to **half of the inter-cell gap**:

`b = g / 2`

Then the outer size becomes:

`L_out = L + 2*b = N*s + (N-1)*g + g = N * (s + g)`

So each module contributes **one full road** `g` per cell in the row/column direction at the outside (two halves meet when two tables abut).

### Example numbers

- `s = 4.9 cm`, `g = 2.4 cm` -> one repeat pitch `s + g = 7.3 cm`.
- `N = 8` -> `L_out = 8 * 7.3 = 58.4 cm` (active grid `L = 55.2 cm`).

### Dual tabletop profiles (~800 mm class modules)

Both layouts are **kept in scope** for later A/B testing (two acrylic / fixture sets). Use one profile at a time; match **`project_config.json`** `grid.rows` / `grid.cols`, **`cell_gap_mm`** (= `g` in mm), and **`border_mm`** (= `g/2` in mm) to the installed plate.

**Convention (unchanged):** `s` ≈ 4.9 cm per 6×6 pocket; modular edge **`b = g/2`**; **`L_out = N(s+g)`** (outer aperture to aperture for the grid module).

| Profile | Road `g` vs cell `s` | `N`×`N` | `L_out` (cm, `s=4.9`) | Role |
|--------|----------------------|---------|------------------------|------|
| **A — dense** | **`g = s/2`** (half 6×6 plate width, ~2.45 cm) | **10×10** | `10×(4.9+2.45)=73.5` | More cells, narrower roads |
| **B — wide road** | **`g = s`** (full plate width as road) | **8×8** | `8×(4.9+4.9)=78.4` | Fewer cells, full-width roads |

The **~800 mm** extrusion / desk footprint can be **larger** than `L_out`; use a **rim** or mask for the difference, or grow `L_out` slightly with tuned `s`/`g` while keeping the same **`N`** and road **ratio** (`g/s`).

Other `N` / `g` pairs for a fixed `L_out` are possible; these two are the **documented reference pair** for side-by-side evaluation.

## Mechanical Tolerance Recommendations

- Cell fixture tolerance: +0.3 to +0.6 mm (on top of the nominal **~4.9 cm** cell size)
- Keep removable top frame for maintenance
- Add cable channels and ventilation under table

## Upgrade Path

1. MVP with single camera and single projector
2. Better camera resolution and optics
3. Multi-camera and multi-projector stitching if needed

