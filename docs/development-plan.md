# Development Plan

## Phase 0 - Requirements Freeze (2-3 days)

- Confirm grid strategy (6x6 or 8x8 unit logic).
- Freeze class-color mapping and building rules.
- Freeze fixed large building footprints.

Deliverables:

- `data-model-and-rules.md` confirmed
- `colors.yaml` and `grid.yaml` drafted

## Phase 1 - Hardware MVP (1-2 weeks)

- Build table frame and camera cavity.
- Install bottom camera and lighting.
- Validate stable image and manual camera lock.

Deliverables:

- Stable rectified frame capture
- Basic per-cell visual debug overlay

## Phase 2 - Detection + Reconstruction (1-2 weeks)

- Implement color classification and smoothing.
- Implement occupancy and connected-component merge.
- Emit state and events over WebSocket.

Deliverables:

- Live `frame_state` and `world_state`
- Logged test sessions for replay

## Phase 3 - Projection Mapping MVP (1 week)

- Build TouchDesigner input and render graph.
- Calibrate projection mapping on physical table.
- Display occupancy and class overlays.

Deliverables:

- Real-time mapped visual output
- Mapping profile saved

## Phase 4 - Simulation + UX (1-2 weeks)

- Add metrics and scenario logic.
- Add visual transitions and confidence feedback.
- Improve operator controls for demos.

Deliverables:

- Scenario dashboard output
- Stable end-to-end demo

## Phase 5 - Hardening (1 week)

- Latency and stability tuning
- Fault handling and restart strategy
- Documentation close-out and runbook

Deliverables:

- Deployment checklist
- Operator guide

