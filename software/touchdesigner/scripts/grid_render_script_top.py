# DKUScope — Script TOP: Grid Cell Renderer
# ────────────────────────────────────────────────────────────────────────────
# File : software/touchdesigner/scripts/grid_render_script_top.py
#
# How to install inside TouchDesigner
# ─────────────────────────────────────
# 1. Create a Script TOP; name it  grid_render_top
# 2. Create a Text DAT with this content; name it  grid_render_script
# 3. On the Script TOP → "Callbacks" parameter → point it to  grid_render_script
#
# Requires:
#   • TouchDesigner 2022.28000 or newer  (copyNumpyArray support)
#   • numpy  (bundled with TD, no install needed)
#   • A Table DAT named  grid_state_table  in the same component
#     rows × cols from live WebSocket state (see ws_callbacks.py)
# ────────────────────────────────────────────────────────────────────────────

import numpy as np


# ── Class colour table ────────────────────────────────────────────────────
# Mirrors the class definitions in software/python/config/project_config.json
# Format: class_id -> (R, G, B, A)  — values 0.0 – 1.0

CLASS_COLORS = {
    0: (0.10,  0.10,  0.10,  1.0),   # Unknown / empty cell
    1: (0.843, 0.227, 0.286, 1.0),   # Academic       #D73A49  红色
    2: (0.545, 0.353, 0.169, 1.0),   # Sports         #8B5A2B  咖啡色
    3: (0.949, 0.800, 0.047, 1.0),   # Dining         #F2CC0C  黄色
    4: (0.184, 0.184, 0.184, 1.0),   # Administrative #2F2F2F  黑色
    5: (0.969, 0.631, 0.769, 1.0),   # Residential    #F7A1C4  粉色
    6: (0.180, 0.627, 0.263, 1.0),   # Green Space    #2EA043  绿色
    7: (0.122, 0.435, 0.922, 1.0),   # Water          #1F6FEB  蓝色
    8: (0.961, 0.961, 0.961, 1.0),   # Road           #F5F5F5  白色
}

CELL_PX = 60    # pixel size of each cell square
GAP_PX  = 2     # gap between adjacent cells
BG_COLOR = (0.05, 0.05, 0.05, 1.0)


# ── Cook function — called every frame by the Script TOP ──────────────────

def cook(scriptOp):
    scriptOp.clearScriptErrors()

    table = op('grid_state_table')
    if table is None:
        scriptOp.addScriptError('grid_state_table DAT not found')
        return

    grid_rows = table.numRows
    grid_cols = table.numCols
    if grid_rows < 1 or grid_cols < 1:
        scriptOp.addScriptError('grid_state_table has invalid dimensions')
        return

    output_w = grid_cols * CELL_PX
    output_h = grid_rows * CELL_PX

    img = np.full((output_h, output_w, 4), BG_COLOR, dtype=np.float32)

    for r in range(grid_rows):
        for c in range(grid_cols):
            try:
                class_id = int(table[r, c])
            except Exception:
                class_id = 8   # fallback: Road

            rgba = CLASS_COLORS.get(class_id, CLASS_COLORS[0])

            y0 = r * CELL_PX + GAP_PX
            y1 = (r + 1) * CELL_PX - GAP_PX
            x0 = c * CELL_PX + GAP_PX
            x1 = (c + 1) * CELL_PX - GAP_PX

            img[y0:y1, x0:x1, 0] = rgba[0]
            img[y0:y1, x0:x1, 1] = rgba[1]
            img[y0:y1, x0:x1, 2] = rgba[2]
            img[y0:y1, x0:x1, 3] = rgba[3]

    scriptOp.copyNumpyArray(img)
