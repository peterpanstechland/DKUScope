# Integration Protocol

## Goal

Define a simple contract between:

- Detection service (Python/OpenCV)
- Simulation service
- Projection renderer (TouchDesigner or other)

## Transport

- WebSocket for state stream
- Optional UDP for low-overhead event burst

## Message Types

1. `frame_state`  
   Full grid snapshot at a lower frequency (e.g., 5-10 Hz).

2. `cell_event`  
   Single-cell stable change event at higher frequency.

3. `world_state`  
   Reconstructed buildings and metrics.

4. `health`  
   Service heartbeat and frame timing.

## `frame_state` Example

```json
{
  "type": "frame_state",
  "seq": 1203,
  "timestamp_ms": 1710000000000,
  "grid": {
    "rows": 16,
    "cols": 16,
    "cells": [
      {"r": 0, "c": 0, "class_id": 8, "conf": 0.97}
    ]
  }
}
```

## `world_state` Example

```json
{
  "type": "world_state",
  "seq": 1203,
  "buildings": [
    {"id": "b_14", "class_id": 3, "cells": [[4,5],[4,6]]}
  ],
  "metrics": {
    "coverage_ratio": 0.42,
    "green_ratio": 0.18
  }
}
```

## Reliability Notes

- Include sequence id and timestamp in all messages.
- Renderer should tolerate dropped events by using periodic snapshots.
- Use last-known-good state fallback on malformed payload.

