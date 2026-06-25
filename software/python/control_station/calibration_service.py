from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class CalibrationResult:
    source_points: List[List[float]]
    destination_points: List[List[float]]
    output_width: int
    output_height: int


def _draw_grid_overlay(
    frame: np.ndarray,
    rows: int,
    cols: int,
    color: tuple[int, int, int] = (0, 255, 255),
) -> np.ndarray:
    if rows <= 0 or cols <= 0:
        return frame
    canvas = frame.copy()
    h, w = canvas.shape[:2]
    for r in range(1, rows):
        y = int(r * h / rows)
        cv2.line(canvas, (0, y), (w, y), color, 1, cv2.LINE_AA)
    for c in range(1, cols):
        x = int(c * w / cols)
        cv2.line(canvas, (x, 0), (x, h), color, 1, cv2.LINE_AA)
    return canvas


def _draw_quad_outline(frame: np.ndarray, points: List[List[float]]) -> np.ndarray:
    if len(points) < 2:
        return frame
    canvas = frame.copy()
    pts = np.array(points, dtype=np.int32)
    if len(points) >= 4:
        cv2.polylines(canvas, [pts], True, (0, 200, 255), 2, cv2.LINE_AA)
    elif len(points) >= 2:
        cv2.polylines(canvas, [pts], False, (0, 200, 255), 2, cv2.LINE_AA)
    return canvas


def _output_size_from_quad(
    points: List[List[float]],
    grid_rows: int,
    grid_cols: int,
    fallback_width: int,
    fallback_height: int,
) -> tuple[int, int]:
    if len(points) != 4:
        return fallback_width, fallback_height

    src = np.array(points, dtype=np.float32)
    top = float(np.linalg.norm(src[1] - src[0]))
    bottom = float(np.linalg.norm(src[2] - src[3]))
    left = float(np.linalg.norm(src[3] - src[0]))
    right = float(np.linalg.norm(src[2] - src[1]))
    avg_w = max((top + bottom) / 2.0, 1.0)
    avg_h = max((left + right) / 2.0, 1.0)

    if grid_rows > 0 and grid_cols > 0:
        aspect = grid_cols / grid_rows
        if avg_w / avg_h >= aspect:
            out_h = int(round(avg_h))
            out_w = int(round(out_h * aspect))
        else:
            out_w = int(round(avg_w))
            out_h = int(round(out_w / aspect))
    else:
        out_w, out_h = int(round(avg_w)), int(round(avg_h))

    max_dim = max(fallback_width, fallback_height)
    scale = max_dim / max(out_w, out_h, 1)
    out_w = max(64, int(round(out_w * scale)))
    out_h = max(64, int(round(out_h * scale)))
    return out_w, out_h


def _destination_points(out_w: int, out_h: int) -> List[List[float]]:
    return [
        [0.0, 0.0],
        [float(out_w - 1), 0.0],
        [float(out_w - 1), float(out_h - 1)],
        [0.0, float(out_h - 1)],
    ]


def _draw_points(frame, points):
    canvas = frame.copy()
    for idx, point in enumerate(points):
        x, y = int(point[0]), int(point[1])
        cv2.circle(canvas, (x, y), 5, (0, 255, 0), -1)
        cv2.putText(
            canvas,
            str(idx + 1),
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    return canvas


def run_four_point_calibration(
    camera_index: int,
    width: int,
    height: int,
    fps: int,
    grid_rows: int = 0,
    grid_cols: int = 0,
) -> Optional[CalibrationResult]:
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    window_name = "Calibration Wizard (click TL->TR->BR->BL, R reset, S save, Q quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1100, 700)

    points: List[List[float]] = []
    current_frame = None

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([float(x), float(y)])

    cv2.setMouseCallback(window_name, on_mouse)

    output_width, output_height = width, height
    destination_points = _destination_points(output_width, output_height)

    result: Optional[CalibrationResult] = None

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        current_frame = frame
        preview = _draw_quad_outline(_draw_points(current_frame, points), points)

        if len(points) == 4:
            output_width, output_height = _output_size_from_quad(
                points, grid_rows, grid_cols, width, height,
            )
            destination_points = _destination_points(output_width, output_height)
            src = np.array(points, dtype=np.float32)
            dst = np.array(destination_points, dtype=np.float32)
            matrix = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(
                current_frame, matrix, (output_width, output_height),
            )
            warped = _draw_grid_overlay(warped, grid_rows, grid_cols)
            show_warped = cv2.resize(warped, (420, 300))
            preview[10 : 10 + show_warped.shape[0], 10 : 10 + show_warped.shape[1]] = show_warped
            cv2.putText(
                preview,
                f"Rectified {output_width}x{output_height} grid {grid_rows}x{grid_cols}",
                (20, 325),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                "If edges are clipped: press R and click OUTSIDE outer cells",
                (20, 350),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

        cv2.imshow(window_name, preview)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("r"), ord("R")):
            points.clear()
        if key in (ord("s"), ord("S")) and len(points) == 4:
            result = CalibrationResult(
                source_points=points.copy(),
                destination_points=destination_points.copy(),
                output_width=output_width,
                output_height=output_height,
            )
            break

    cap.release()
    cv2.destroyWindow(window_name)
    return result

