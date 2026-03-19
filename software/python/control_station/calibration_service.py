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

    destination_points = [
        [0.0, 0.0],
        [float(width - 1), 0.0],
        [float(width - 1), float(height - 1)],
        [0.0, float(height - 1)],
    ]

    result: Optional[CalibrationResult] = None

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        current_frame = frame
        preview = _draw_points(current_frame, points)

        if len(points) == 4:
            src = np.array(points, dtype=np.float32)
            dst = np.array(destination_points, dtype=np.float32)
            matrix = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(current_frame, matrix, (width, height))
            show_warped = cv2.resize(warped, (420, 300))
            preview[10 : 10 + show_warped.shape[0], 10 : 10 + show_warped.shape[1]] = show_warped
            cv2.putText(
                preview,
                "Preview rectified view (top-left overlay)",
                (20, 325),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
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
                output_width=width,
                output_height=height,
            )
            break

    cap.release()
    cv2.destroyWindow(window_name)
    return result

