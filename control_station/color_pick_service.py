from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


SAMPLE_RADIUS = 15


@dataclass
class ColorSampleResult:
    lab_values: List[float]
    bgr_values: List[int]
    hex_color: str


def _bgr_to_hex(b: int, g: int, r: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _draw_sampled_info(frame, samples: List[dict]):
    for s in samples:
        x, y = s["x"], s["y"]
        cv2.circle(frame, (x, y), SAMPLE_RADIUS, (0, 255, 0), 2)
        cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)
        lab = s["lab"]
        text = f"L:{lab[0]:.0f} a:{lab[1]:.0f} b:{lab[2]:.0f}"
        cv2.putText(
            frame, text, (x + SAMPLE_RADIUS + 4, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA,
        )
    return frame


def _draw_hover_info(frame, x: int, y: int):
    h, w = frame.shape[:2]
    x = max(SAMPLE_RADIUS, min(x, w - SAMPLE_RADIUS - 1))
    y = max(SAMPLE_RADIUS, min(y, h - SAMPLE_RADIUS - 1))

    roi = frame[
        y - SAMPLE_RADIUS : y + SAMPLE_RADIUS + 1,
        x - SAMPLE_RADIUS : x + SAMPLE_RADIUS + 1,
    ]
    lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2Lab)
    median_lab = np.median(lab_roi.reshape(-1, 3), axis=0)
    median_bgr = np.median(roi.reshape(-1, 3), axis=0).astype(int)

    cv2.rectangle(
        frame,
        (x - SAMPLE_RADIUS, y - SAMPLE_RADIUS),
        (x + SAMPLE_RADIUS, y + SAMPLE_RADIUS),
        (255, 255, 0), 1,
    )

    info = (
        f"Lab({median_lab[0]:.0f},{median_lab[1]:.0f},{median_lab[2]:.0f}) "
        f"BGR({median_bgr[0]},{median_bgr[1]},{median_bgr[2]})"
    )
    cv2.putText(
        frame, info, (10, h - 15),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1, cv2.LINE_AA,
    )

    swatch_size = 40
    swatch = np.full((swatch_size, swatch_size, 3), median_bgr, dtype=np.uint8)
    frame[10 : 10 + swatch_size, w - 10 - swatch_size : w - 10] = swatch
    return frame


def run_color_pick(
    camera_index: int,
    width: int,
    height: int,
    fps: int,
    class_label: str = "",
) -> Optional[ColorSampleResult]:
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    title = f"Color Pick: {class_label}" if class_label else "Color Pick"
    window_name = f"{title} (click to sample, R reset, S save, Q quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 640)

    samples: List[dict] = []
    hover_pos = [width // 2, height // 2]

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_MOUSEMOVE:
            hover_pos[0] = x
            hover_pos[1] = y
        elif event == cv2.EVENT_LBUTTONDOWN:
            h, w = current_frame.shape[:2]
            cx = max(SAMPLE_RADIUS, min(x, w - SAMPLE_RADIUS - 1))
            cy = max(SAMPLE_RADIUS, min(y, h - SAMPLE_RADIUS - 1))
            roi = current_frame[
                cy - SAMPLE_RADIUS : cy + SAMPLE_RADIUS + 1,
                cx - SAMPLE_RADIUS : cx + SAMPLE_RADIUS + 1,
            ]
            lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2Lab)
            median_lab = np.median(lab_roi.reshape(-1, 3), axis=0).tolist()
            samples.append({"x": cx, "y": cy, "lab": median_lab})

    cv2.setMouseCallback(window_name, on_mouse)
    current_frame = np.zeros((height, width, 3), dtype=np.uint8)
    result: Optional[ColorSampleResult] = None

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        current_frame = frame.copy()
        preview = current_frame.copy()

        preview = _draw_hover_info(preview, hover_pos[0], hover_pos[1])
        preview = _draw_sampled_info(preview, samples)

        n = len(samples)
        guide = f"Samples: {n}  |  Click to add  |  R=reset  S=save  Q=quit"
        cv2.putText(
            preview, guide, (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1, cv2.LINE_AA,
        )

        cv2.imshow(window_name, preview)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("r"), ord("R")):
            samples.clear()
        if key in (ord("s"), ord("S")) and samples:
            all_labs = np.array([s["lab"] for s in samples])
            avg_lab = np.mean(all_labs, axis=0).tolist()

            avg_lab_pixel = np.array([[avg_lab]], dtype=np.float32).astype(np.uint8)
            avg_bgr_pixel = cv2.cvtColor(avg_lab_pixel, cv2.COLOR_Lab2BGR)
            b, g, r = int(avg_bgr_pixel[0, 0, 0]), int(avg_bgr_pixel[0, 0, 1]), int(avg_bgr_pixel[0, 0, 2])

            result = ColorSampleResult(
                lab_values=avg_lab,
                bgr_values=[b, g, r],
                hex_color=_bgr_to_hex(b, g, r),
            )
            break

    cap.release()
    cv2.destroyWindow(window_name)
    return result
