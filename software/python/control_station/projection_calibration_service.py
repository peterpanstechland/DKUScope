"""
Projection mapping calibration using a top-mounted camera.

Flow:
1. Generate a chessboard pattern image at projector resolution.
2. Display it fullscreen on the projector output.
3. Capture from top camera -> detect chessboard corners.
4. Compute homography between projected pattern and detected corners.
5. Return warp matrix that can pre-distort content before projection.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ProjectionCalibrationResult:
    source_points: List[List[float]]
    destination_points: List[List[float]]
    warp_matrix: List[List[float]]


def generate_chessboard_image(
    width: int, height: int, cols: int, rows: int,
) -> Tuple[np.ndarray, np.ndarray]:
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    margin_x = width // 8
    margin_y = height // 8
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y
    sq_w = inner_w / (cols + 1)
    sq_h = inner_h / (rows + 1)

    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                x1 = int(margin_x + c * sq_w)
                y1 = int(margin_y + r * sq_h)
                x2 = int(margin_x + (c + 1) * sq_w)
                y2 = int(margin_y + (r + 1) * sq_h)
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), -1)

    ideal_corners = np.zeros((rows * cols, 2), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            ideal_corners[r * cols + c] = [
                margin_x + (c + 1) * sq_w,
                margin_y + (r + 1) * sq_h,
            ]

    return img, ideal_corners


def run_projection_calibration(
    projector_width: int,
    projector_height: int,
    camera_index: int,
    camera_width: int = 640,
    camera_height: int = 480,
    camera_fps: int = 30,
    pattern_cols: int = 9,
    pattern_rows: int = 6,
) -> Optional[ProjectionCalibrationResult]:
    pattern_img, ideal_corners = generate_chessboard_image(
        projector_width, projector_height, pattern_cols, pattern_rows,
    )
    pattern_size = (pattern_cols, pattern_rows)

    proj_window = "Projector Output (move to projector screen)"
    cv2.namedWindow(proj_window, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(proj_window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow(proj_window, pattern_img)
    cv2.waitKey(500)

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cv2.destroyWindow(proj_window)
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
    cap.set(cv2.CAP_PROP_FPS, camera_fps)

    cam_window = "Top Camera (press C to capture, Q to quit)"
    cv2.namedWindow(cam_window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(cam_window, 800, 600)

    result: Optional[ProjectionCalibrationResult] = None
    detected_corners = None

    time.sleep(1.0)

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        preview = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, pattern_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
        )

        if found:
            corners = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
            )
            cv2.drawChessboardCorners(preview, pattern_size, corners, found)
            detected_corners = corners.reshape(-1, 2)
            status = f"Detected {pattern_cols}x{pattern_rows} corners - press C to confirm"
        else:
            detected_corners = None
            status = "Searching for chessboard..."

        cv2.putText(
            preview, status, (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA,
        )
        cv2.imshow(cam_window, preview)
        cv2.imshow(proj_window, pattern_img)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("c"), ord("C")) and detected_corners is not None:
            src = detected_corners.astype(np.float32)
            dst = ideal_corners.astype(np.float32)

            matrix, _mask = cv2.findHomography(src, dst)
            if matrix is not None:
                result = ProjectionCalibrationResult(
                    source_points=src.tolist(),
                    destination_points=dst.tolist(),
                    warp_matrix=matrix.tolist(),
                )

                warped = cv2.warpPerspective(frame, matrix, (projector_width, projector_height))
                cv2.imshow(proj_window, warped)
                cv2.waitKey(2000)
            break

    cap.release()
    cv2.destroyWindow(cam_window)
    cv2.destroyWindow(proj_window)
    return result
