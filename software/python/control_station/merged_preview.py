from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class MergedSlice:
    unit_id: str
    frame: np.ndarray
    row_offset: int
    col_offset: int
    local_rows: int
    local_cols: int


def build_merged_preview(
    slices: List[MergedSlice],
    total_rows: int,
    total_cols: int,
    max_width: int = 480,
) -> Optional[np.ndarray]:
    """Stitch calibrated (warped) unit frames into one global grid mosaic."""
    if total_rows <= 0 or total_cols <= 0:
        return None

    cell_px = max(24, max_width // total_cols)
    out_w = total_cols * cell_px
    out_h = total_rows * cell_px
    mosaic = np.full((out_h, out_w, 3), 28, dtype=np.uint8)

    for sl in slices:
        if sl.frame is None or sl.frame.size == 0:
            continue
        tw = sl.local_cols * cell_px
        th = sl.local_rows * cell_px
        resized = cv2.resize(sl.frame, (tw, th), interpolation=cv2.INTER_AREA)
        y0 = sl.row_offset * cell_px
        x0 = sl.col_offset * cell_px
        y1 = min(y0 + th, out_h)
        x1 = min(x0 + tw, out_w)
        mosaic[y0:y1, x0:x1] = resized[: y1 - y0, : x1 - x0]
        cv2.putText(
            mosaic,
            sl.unit_id,
            (x0 + 4, y0 + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    for r in range(total_rows + 1):
        y = r * cell_px
        cv2.line(mosaic, (0, y), (out_w, y), (0, 200, 0), 1, cv2.LINE_AA)
    for c in range(total_cols + 1):
        x = c * cell_px
        cv2.line(mosaic, (x, 0), (x, out_h), (0, 200, 0), 1, cv2.LINE_AA)

    return mosaic
