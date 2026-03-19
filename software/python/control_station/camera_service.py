from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class CameraInfo:
    index: int
    name: str


def _opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
    except Exception:
        return False
    return True


def enumerate_cameras(max_indices: int = 10) -> List[CameraInfo]:
    if not _opencv_available():
        return []

    import cv2

    cameras: List[CameraInfo] = []
    for idx in range(max_indices):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        ok, _frame = cap.read()
        cap.release()
        if ok:
            cameras.append(CameraInfo(index=idx, name=f"Camera {idx}"))
    return cameras


def test_camera(index: int, width: int, height: int, fps: int) -> bool:
    if not _opencv_available():
        return False

    import cv2

    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    ok, _frame = cap.read()
    cap.release()
    return bool(ok)

