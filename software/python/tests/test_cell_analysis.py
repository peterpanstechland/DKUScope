from __future__ import annotations

import numpy as np

from control_station.cell_analysis import (
    analyze_cell,
    build_block_mask,
    is_empty_cell,
)
from control_station.config_schema import DetectionConfig


def _make_lab_frame(rows: int, cols: int, cell_lab: tuple[float, float, float]) -> np.ndarray:
    h, w = rows * 40, cols * 40
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    l, a, b = cell_lab
    frame[:, :] = [l, a, b]
    return frame


def test_empty_cell_when_matches_background():
    config = DetectionConfig()
    ref = np.array([120.0, 128.0, 128.0], dtype=np.float64)
    lab_frame = _make_lab_frame(2, 2, (120, 128, 128))
    result = analyze_cell(lab_frame, 0, 0, 2, 2, config, ref_lab=ref)
    assert result.is_empty or not result.occupied


def test_occupied_cell_with_colored_block():
    config = DetectionConfig(background_delta_threshold=10.0, min_block_area_ratio=0.05)
    ref = np.array([120.0, 128.0, 128.0], dtype=np.float64)
    lab_frame = _make_lab_frame(2, 2, (120, 128, 128))
    h, w = lab_frame.shape[:2]
    lab_frame[h // 4: 3 * h // 4, w // 4: 3 * w // 4] = [80, 200, 130]
    result = analyze_cell(lab_frame, 0, 0, 2, 2, config, ref_lab=ref)
    assert result.occupied
    assert not result.is_empty


def test_glare_pixels_excluded_from_mask():
    config = DetectionConfig(glare_l_threshold=240, glare_chroma_max=15)
    roi = np.zeros((20, 20, 3), dtype=np.uint8)
    roi[:, :] = [120, 128, 128]
    roi[5:10, 5:10] = [250, 128, 128]
    ref = np.array([120.0, 128.0, 128.0], dtype=np.float64)
    mask = build_block_mask(roi, ref, config)
    assert mask[7, 7] == 0


def test_is_empty_cell_helper():
    ref = np.array([100.0, 128.0, 128.0])
    cell = np.array([102.0, 129.0, 127.0])
    assert is_empty_cell(cell, ref, delta_threshold=18.0)
