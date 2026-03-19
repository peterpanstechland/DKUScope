from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from control_station.config_manager import load_config


def draw_grid(frame, rows: int, cols: int):
    h, w = frame.shape[:2]
    cell_h = h / rows
    cell_w = w / cols
    for r in range(1, rows):
        y = int(r * cell_h)
        cv2.line(frame, (0, y), (w, y), (120, 120, 120), 1)
    for c in range(1, cols):
        x = int(c * cell_w)
        cv2.line(frame, (x, 0), (x, h), (120, 120, 120), 1)
    return frame


def main():
    parser = argparse.ArgumentParser(description="Camera grid probe and preview tool")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/project_config.json"),
        help="Path to project config json",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    cap = cv2.VideoCapture(cfg.camera.index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.camera.fps)

    if not cap.isOpened():
        print("Failed to open camera.")
        return

    print("Press Q to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        preview = frame.copy()
        preview = draw_grid(preview, cfg.grid.rows, cfg.grid.cols)
        cv2.imshow("DKUScope Camera Grid Probe", preview)
        if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

