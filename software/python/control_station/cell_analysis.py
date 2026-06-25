from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .config_schema import DetectionConfig


@dataclass
class CellAnalysisResult:
    lab_median: np.ndarray
    occupied: bool
    mask_area_ratio: float
    is_empty: bool


def apply_clahe_bgr(frame: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2Lab)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge([l_channel, a_channel, b_channel])
    return cv2.cvtColor(merged, cv2.COLOR_Lab2BGR)


def preprocess_frame(frame: np.ndarray, config: DetectionConfig) -> np.ndarray:
    if config.use_clahe:
        return apply_clahe_bgr(frame, clip_limit=config.clahe_clip_limit)
    return frame


def _cell_bounds(
    r: int, c: int, rows: int, cols: int, h: int, w: int, margin_ratio: float,
) -> Tuple[int, int, int, int]:
    cell_h = h / rows
    cell_w = w / cols
    y1 = int(r * cell_h + cell_h * margin_ratio)
    y2 = int((r + 1) * cell_h - cell_h * margin_ratio)
    x1 = int(c * cell_w + cell_w * margin_ratio)
    x2 = int((c + 1) * cell_w - cell_w * margin_ratio)
    return y1, y2, x1, x2


def _chroma_map(lab_roi: np.ndarray) -> np.ndarray:
    a = lab_roi[:, :, 1].astype(np.float32) - 128.0
    b = lab_roi[:, :, 2].astype(np.float32) - 128.0
    return np.sqrt(a * a + b * b)


def build_block_mask(
    lab_roi: np.ndarray,
    ref_lab: Optional[np.ndarray],
    config: DetectionConfig,
) -> np.ndarray:
    h, w = lab_roi.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    chroma = _chroma_map(lab_roi)
    if ref_lab is not None:
        diff = lab_roi.astype(np.float32) - ref_lab.astype(np.float32)
        ab_dist = np.sqrt(diff[:, :, 1] ** 2 + diff[:, :, 2] ** 2)
        mask = np.where(
            (ab_dist > config.background_delta_threshold) | (chroma > config.chroma_threshold),
            255,
            0,
        ).astype(np.uint8)
    else:
        mask = np.where(chroma > config.chroma_threshold, 255, 0).astype(np.uint8)

    if config.glare_filter_enabled:
        glare = (lab_roi[:, :, 0] > config.glare_l_threshold) & (chroma < config.glare_chroma_max)
        mask[glare] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def is_empty_cell(
    cell_lab: np.ndarray,
    ref_lab: np.ndarray,
    delta_threshold: float,
) -> bool:
    return float(np.linalg.norm(cell_lab.astype(np.float64) - ref_lab.astype(np.float64))) < delta_threshold


def analyze_cell(
    lab_frame: np.ndarray,
    r: int,
    c: int,
    rows: int,
    cols: int,
    config: DetectionConfig,
    ref_lab: Optional[np.ndarray] = None,
) -> CellAnalysisResult:
    h, w = lab_frame.shape[:2]
    y1, y2, x1, x2 = _cell_bounds(r, c, rows, cols, h, w, config.margin_ratio)
    lab_roi = lab_frame[y1:y2, x1:x2]
    if lab_roi.size == 0:
        empty_lab = np.array([0.0, 128.0, 128.0], dtype=np.float64)
        return CellAnalysisResult(empty_lab, False, 0.0, True)

    full_median = np.median(lab_roi.reshape(-1, 3), axis=0)
    is_empty = False
    if ref_lab is not None:
        dist = float(np.linalg.norm(full_median - ref_lab))
        if dist < config.background_delta_threshold:
            is_empty = True

    mask = build_block_mask(lab_roi, ref_lab, config)
    area_ratio = float(np.count_nonzero(mask)) / float(mask.size)

    if area_ratio < config.min_block_area_ratio:
        return CellAnalysisResult(full_median, False, area_ratio, True)

    masked_pixels = lab_roi[mask > 0]
    if masked_pixels.size == 0:
        return CellAnalysisResult(full_median, False, area_ratio, True)

    lab_median = np.median(masked_pixels.reshape(-1, 3), axis=0)
    if area_ratio >= config.min_block_area_ratio:
        is_empty = False
    return CellAnalysisResult(lab_median, True, area_ratio, is_empty)
