# DKUScope — WebSocket DAT Callbacks
# ────────────────────────────────────────────────────────────────────────────
# File : software/touchdesigner/scripts/ws_callbacks.py
#
# How to install inside TouchDesigner
# ─────────────────────────────────────
# 1. Create a Text DAT anywhere in your network; name it  ws_callbacks
# 2. Paste the ENTIRE content of this file into it
# 3. Select your WebSocket DAT (ws_receiver)
# 4. In the Parameters panel → "Callbacks DAT" → point it to  ws_callbacks
#
# This script receives every JSON message from the Python detection server,
# parses it, and writes the result to the Table DAT named  grid_state_table
#     rows × cols from live WebSocket state (see frame_state message).
# ────────────────────────────────────────────────────────────────────────────

import json


def onReceiveText(dat, rowIndex, message):
    """Triggered once per incoming WebSocket text frame."""
    try:
        payload = json.loads(message)
    except Exception as e:
        print(f'[ws_callbacks] JSON parse error: {e}')
        return

    msg_type = payload.get('type', '')

    if msg_type == 'frame_state':
        _handle_frame_state(payload)
    elif msg_type == 'world_state':
        _handle_world_state(payload)
    # 'health' messages are silently ignored


# ── frame_state handler ───────────────────────────────────────────────────

def _handle_frame_state(payload):
    """
    Updates grid_state_table from a frame_state message.

    Expected payload shape:
      { "type": "frame_state",
        "grid": { "rows": 4, "cols": 8,
                  "cells": [{"r":0,"c":0,"class_id":8,"conf":0.97}, ...] } }
    """
    grid  = payload.get('grid', {})
    rows  = grid.get('rows', 4)
    cols  = grid.get('cols', 8)
    cells = grid.get('cells', [])

    table = op('grid_state_table')
    if table is None:
        print('[ws_callbacks] ERROR: grid_state_table DAT not found in the network')
        return

    # Re-initialise table dimensions when the grid config changes
    if table.numRows != rows or table.numCols != cols:
        table.clear()
        for _ in range(rows):
            table.appendRow([0] * cols)   # 0 = empty cell (default)

    for cell in cells:
        r        = cell.get('r', cell.get('row', 0))
        c        = cell.get('c', cell.get('col', 0))
        class_id = int(cell.get('class_id', 0))
        try:
            table[r, c] = class_id
        except Exception as e:
            print(f'[ws_callbacks] table write error r={r} c={c}: {e}')


# ── world_state handler ───────────────────────────────────────────────────

def _handle_world_state(payload):
    """
    Stores building entities and metrics in component storage for
    optional overlay layers to consume.

    Expected payload shape:
      { "type": "world_state",
        "buildings": [{"id":"b_1","class_id":3,"cells":[[4,5],[4,6]]}, ...],
        "metrics":   {"coverage_ratio":0.42, "green_ratio":0.18} }
    """
    comp = op('/project1') or op('/')
    comp.store('world_buildings', payload.get('buildings', []))
    comp.store('world_metrics',   payload.get('metrics',   {}))


# ── connection lifecycle ───────────────────────────────────────────────────

def onConnect(dat):
    print(f'[DKUScope WS] Connected → {dat.par.netaddress}:{dat.par.port}')
    ui.status = 'DKUScope: WS connected'


def onDisconnect(dat):
    print('[DKUScope WS] Disconnected')
    ui.status = 'DKUScope: WS disconnected'


def onConnectFailed(dat):
    print('[DKUScope WS] Connection FAILED')
    print('  Is the Python server running?  →  python software/python/main.py')
    ui.status = 'DKUScope: WS connection failed'
