# DKUScope — TouchDesigner Network Auto-Builder
# ────────────────────────────────────────────────────────────────────────────
# File : software/touchdesigner/bootstrap/create_network.py
#
# HOW TO RUN  (Two-step method)
# ──────────────────────────────
# TD operator types (websocketDAT etc.) only exist inside DAT script context,
# NOT when using exec() from the Textport. Use this two-step method:
#
# Step A — paste this ONE LINE in the Textport (Alt+T):
#
#   t = op('/project1').create(textDAT, 'dku_builder'); t.text = open('C:/Users/Twink/OneDrive/Documents/Robomon/DKUScope/software/touchdesigner/bootstrap/create_network.py').read()
#
# Step B — right-click the yellow 'dku_builder' Text DAT → Run Script
#
# ALTERNATIVE: copy-paste the ENTIRE content of this file directly into the
#              Textport and press Enter. Direct paste also has TD globals.
#
# WHAT IT CREATES
# ────────────────
#   ws_receiver       WebSocket DAT    — connects to ws://localhost:8765
#   ws_callbacks      Text DAT         — callback logic (JSON parser → table)
#   grid_state_table  Table DAT        — live grid state (class_ids)
#   grid_render_script Text DAT        — Script TOP render code
#   grid_render_top   Script TOP       — renders coloured grid (dynamic size)
#   level_top         Level TOP        — brightness/contrast adjustment
#   null_output       Null TOP         — final output tap (wire projector here)
#
# After running, wire  null_output  to a Window COMP for projector fullscreen.
# ────────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# EMBEDDED SCRIPTS  (these strings are written into Text DATs by the builder)
# ═══════════════════════════════════════════════════════════════════════════

_WS_CALLBACKS_SCRIPT = '''\
import json

def onReceiveText(dat, rowIndex, message):
    try:
        payload = json.loads(message)
    except Exception as e:
        print(f"[ws_callbacks] JSON parse error: {e}")
        return
    msg_type = payload.get("type", "")
    if msg_type == "frame_state":
        _handle_frame_state(payload)
    elif msg_type == "world_state":
        _handle_world_state(payload)

def _handle_frame_state(payload):
    grid  = payload.get("grid", {})
    rows  = grid.get("rows", 4)
    cols  = grid.get("cols", 8)
    cells = grid.get("cells", [])
    table = op("grid_state_table")
    if table is None:
        print("[ws_callbacks] ERROR: grid_state_table not found")
        return
    if table.numRows != rows or table.numCols != cols:
        table.clear()
        for _ in range(rows):
            table.appendRow([8] * cols)
    for cell in cells:
        r        = cell.get("r", 0)
        c        = cell.get("c", 0)
        class_id = int(cell.get("class_id", 8))
        try:
            table[r, c] = class_id
        except Exception as e:
            print(f"[ws_callbacks] table write error r={r} c={c}: {e}")

def _handle_world_state(payload):
    comp = op("/project1") or op("/")
    comp.store("world_buildings", payload.get("buildings", []))
    comp.store("world_metrics",   payload.get("metrics",   {}))

def onConnect(dat):
    print(f"[DKUScope WS] Connected to {dat.par.netaddress}:{dat.par.port}")
    ui.status = "DKUScope: WS connected"

def onDisconnect(dat):
    print("[DKUScope WS] Disconnected")
    ui.status = "DKUScope: WS disconnected"

def onConnectFailed(dat):
    print("[DKUScope WS] Connection FAILED — is the Python server running?")
    ui.status = "DKUScope: WS connection failed"
'''


_RENDER_SCRIPT = '''\
import numpy as np

CLASS_COLORS = {
    0: (0.10,  0.10,  0.10,  1.0),
    1: (0.843, 0.227, 0.286, 1.0),
    2: (0.545, 0.353, 0.169, 1.0),
    3: (0.949, 0.800, 0.047, 1.0),
    4: (0.184, 0.184, 0.184, 1.0),
    5: (0.969, 0.631, 0.769, 1.0),
    6: (0.180, 0.627, 0.263, 1.0),
    7: (0.122, 0.435, 0.922, 1.0),
    8: (0.961, 0.961, 0.961, 1.0),
}

CELL_PX = 60
GAP_PX  = 2

def cook(scriptOp):
    scriptOp.clearScriptErrors()
    table = op("grid_state_table")
    if table is None:
        scriptOp.addScriptError("grid_state_table not found")
        return
    grid_rows = table.numRows
    grid_cols = table.numCols
    if grid_rows < 1 or grid_cols < 1:
        scriptOp.addScriptError("grid_state_table has invalid dimensions")
        return
    output_w = grid_cols * CELL_PX
    output_h = grid_rows * CELL_PX
    img = np.full((output_h, output_w, 4), (0.05, 0.05, 0.05, 1.0), dtype=np.float32)
    for r in range(grid_rows):
        for c in range(grid_cols):
            try:
                class_id = int(table[r, c])
            except Exception:
                class_id = 8
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
'''


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _destroy_if_exists(base, name):
    if base is None:
        return
    existing = base.op(name)
    if existing is not None:
        existing.destroy()


def create_dkuscope_network():
    # parent() returns None when called from Textport directly;
    # fall back to /project1, then root.
    base = op('/project1') or op('/')

    print('=' * 60)
    print('DKUScope — Building TD network...')
    print('=' * 60)

    # ── Cleanup previous run ───────────────────────────────────────────────
    for name in ['ws_receiver', 'ws_callbacks', 'grid_state_table',
                 'grid_render_script', 'grid_render_top',
                 'level_top', 'null_output']:
        _destroy_if_exists(base, name)

    # ── 1. WebSocket DAT ───────────────────────────────────────────────────
    ws = base.create(websocketDAT, 'ws_receiver')
    ws.par.active     = True
    ws.par.netaddress = 'localhost'
    ws.par.port       = 8765
    ws.nodeX = -500
    ws.nodeY = 0
    print('  ✓ ws_receiver  (WebSocket DAT → localhost:8765)')

    # ── 2. Callbacks Text DAT ──────────────────────────────────────────────
    cb = base.create(textDAT, 'ws_callbacks')
    cb.text  = _WS_CALLBACKS_SCRIPT
    cb.nodeX = -500
    cb.nodeY = -200
    ws.par.callbacks = cb
    print('  ✓ ws_callbacks  (Text DAT — callback logic)')

    # ── 3. Grid State Table DAT ────────────────────────────────────────────
    tbl = base.create(tableDAT, 'grid_state_table')
    tbl.clear()
    default_rows = 4
    default_cols = 8
    for _ in range(default_rows):
        tbl.appendRow([8] * default_cols)
    tbl.nodeX = -100
    tbl.nodeY = 0
    print(f'  ✓ grid_state_table  (Table DAT — {default_rows}×{default_cols}, default Road)')

    # ── 4. Render Script Text DAT ──────────────────────────────────────────
    rs = base.create(textDAT, 'grid_render_script')
    rs.text  = _RENDER_SCRIPT
    rs.nodeX = 200
    rs.nodeY = -200
    print('  ✓ grid_render_script  (Text DAT — Script TOP source)')

    # ── 5. Script TOP ──────────────────────────────────────────────────────
    sTop = base.create(scriptTOP, 'grid_render_top')
    sTop.par.callbacks = rs
    sTop.nodeX = 200
    sTop.nodeY = 0
    print('  ✓ grid_render_top  (Script TOP — dynamic grid render)')

    # ── 6. Level TOP (brightness / contrast tweaks for projection) ─────────
    lvl = base.create(levelTOP, 'level_top')
    lvl.inputConnectors[0].connect(sTop)
    lvl.nodeX = 500
    lvl.nodeY = 0
    print('  ✓ level_top  (Level TOP — adjust brightness for projector)')

    # ── 7. Null TOP (final output tap) ─────────────────────────────────────
    out = base.create(nullTOP, 'null_output')
    out.inputConnectors[0].connect(lvl)
    out.nodeX = 700
    out.nodeY = 0
    print('  ✓ null_output  (Null TOP — wire this to a Window COMP)')

    print('=' * 60)
    print('Network created successfully!')
    print()
    print('NEXT STEPS:')
    print('  1. Start the Python detection server')
    print('     →  cd software/python && python main.py')
    print('  2. The ws_receiver will auto-connect to ws://localhost:8765')
    print('  3. Add a Window COMP and set input to null_output for projector')
    print('  4. (Optional) Insert a Warp TOP between level_top and null_output')
    print('     after running projection calibration in the Python UI')
    print('=' * 60)


# Run immediately when the script is executed / pasted into Textport
create_dkuscope_network()
