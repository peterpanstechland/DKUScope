"""
DKUScope Projection Mapping Calibration (standalone)

1. Projects a chessboard pattern via projector
2. Top camera captures it from above
3. Detects corners and computes warp matrix
4. Saves result to config

Usage:
    python scripts/run_projection_calibration.py
    python scripts/run_projection_calibration.py --proj-cam 1 --proj-w 1920 --proj-h 1080
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from control_station.config_manager import load_config, save_config
from control_station.projection_calibration_service import run_projection_calibration


def main() -> None:
    parser = argparse.ArgumentParser(description="DKUScope Projection Calibration")
    parser.add_argument(
        "--config", type=Path, default=Path("config/project_config.json"),
    )
    parser.add_argument("--proj-cam", type=int, default=None, help="Top camera index for projection calibration")
    parser.add_argument("--proj-w", type=int, default=None, help="Projector width")
    parser.add_argument("--proj-h", type=int, default=None, help="Projector height")
    parser.add_argument("--pattern-cols", type=int, default=None)
    parser.add_argument("--pattern-rows", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    proj = config.projection

    cam_idx = args.proj_cam if args.proj_cam is not None else proj.projector_camera_index
    pw = args.proj_w if args.proj_w is not None else proj.projector_width
    ph = args.proj_h if args.proj_h is not None else proj.projector_height
    pcols = args.pattern_cols if args.pattern_cols is not None else proj.pattern_cols
    prows = args.pattern_rows if args.pattern_rows is not None else proj.pattern_rows

    print(f"Projector: {pw}x{ph}, Top camera: {cam_idx}, Pattern: {pcols}x{prows}")
    print("Move the 'Projector Output' window to your projector screen, then press C to confirm.")

    result = run_projection_calibration(
        projector_width=pw,
        projector_height=ph,
        camera_index=cam_idx,
        pattern_cols=pcols,
        pattern_rows=prows,
    )

    if result is None:
        print("Calibration cancelled or failed.")
        return

    config.projection.enabled = True
    config.projection.source_points = result.source_points
    config.projection.destination_points = result.destination_points
    config.projection.warp_matrix = result.warp_matrix
    config.projection.projector_camera_index = cam_idx
    config.projection.projector_width = pw
    config.projection.projector_height = ph
    config.projection.pattern_cols = pcols
    config.projection.pattern_rows = prows

    path = save_config(config, args.config)
    print(f"Projection calibration saved to {path}")
    print(f"Warp matrix (3x3): {json.dumps(result.warp_matrix, indent=2)}")


if __name__ == "__main__":
    main()
