from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .background_refs import BackgroundRef, load_background_refs
from .merged_preview import MergedSlice, build_merged_preview
from .cell_analysis import analyze_cell, preprocess_frame
from .color_profile import (
    ensure_class_color_profile,
    lab_ab_distance,
    lab_distance,
    lab_in_range,
    range_diagonal,
)
from .config_schema import BuildingClassConfig, CalibrationConfig, DetectionConfig, ProjectConfig


TEMPORAL_WINDOW = 3
EMPTY_CLASS_ID = 0
EMPTY_LABEL = "empty"


@dataclass
class CellResult:
    row: int
    col: int
    class_id: int
    label: str
    confidence: float
    occupied: bool = True
    mask_area_ratio: float = 0.0


@dataclass
class FrameResult:
    seq: int
    timestamp_ms: int
    rows: int
    cols: int
    cells: List[CellResult]
    changed_cells: List[CellResult] = field(default_factory=list)
    debug_frame: Optional[np.ndarray] = None
    merged_preview: Optional[np.ndarray] = None


class ColorClassifier:
    def __init__(
        self,
        classes: List[BuildingClassConfig],
        detection: DetectionConfig,
    ) -> None:
        self._detection = detection
        self._profiles: List[Tuple[int, np.ndarray, np.ndarray, np.ndarray, str]] = []
        self._centroids: List[Tuple[int, np.ndarray, str]] = []

        for cls_cfg in classes:
            ensure_class_color_profile(
                cls_cfg,
                l_padding=detection.color_range_l_padding,
                ab_padding=detection.color_range_ab_padding,
            )
            if cls_cfg.lab_centroid and len(cls_cfg.lab_centroid) == 3:
                centroid = np.array(cls_cfg.lab_centroid, dtype=np.float64)
                self._centroids.append((cls_cfg.class_id, centroid, cls_cfg.label))
                if cls_cfg.lab_min and cls_cfg.lab_max and len(cls_cfg.lab_min) == 3:
                    self._profiles.append((
                        cls_cfg.class_id,
                        centroid,
                        np.array(cls_cfg.lab_min, dtype=np.float64),
                        np.array(cls_cfg.lab_max, dtype=np.float64),
                        cls_cfg.label,
                    ))

        if not self._centroids:
            raise ValueError(
                "No classes have calibrated Lab values. "
                "Use the control station to sample colors first."
            )

    def classify(self, lab_median: np.ndarray) -> Tuple[int, str, float]:
        threshold = self._detection.confidence_threshold
        l_weight = self._detection.color_match_l_weight
        box_matches: List[Tuple[int, str, float, float]] = []

        for class_id, centroid, lab_min, lab_max, label in self._profiles:
            if lab_in_range(lab_median, lab_min.tolist(), lab_max.tolist()):
                dist = lab_distance(lab_median, centroid, l_weight=l_weight)
                ab_dist = lab_ab_distance(lab_median, centroid)
                diag = range_diagonal(lab_min.tolist(), lab_max.tolist())
                confidence = max(0.0, 1.0 - dist / diag)
                box_matches.append((class_id, label, confidence, ab_dist))

        if box_matches:
            box_matches.sort(key=lambda m: (m[3], -m[2]))
            best = box_matches[0]
            return best[0], best[1], best[2]

        best_id = -1
        best_label = "unknown"
        best_ab_dist = float("inf")
        best_weighted_dist = float("inf")
        for class_id, centroid, label in self._centroids:
            ab_dist = lab_ab_distance(lab_median, centroid)
            weighted_dist = lab_distance(lab_median, centroid, l_weight=l_weight)
            if ab_dist < best_ab_dist or (
                ab_dist == best_ab_dist and weighted_dist < best_weighted_dist
            ):
                best_ab_dist = ab_dist
                best_weighted_dist = weighted_dist
                best_id = class_id
                best_label = label

        confidence = max(0.0, 1.0 - best_weighted_dist / 200.0)
        if best_ab_dist > threshold:
            return -1, "unknown", confidence
        return best_id, best_label, confidence


class GridDetector:
    def __init__(
        self,
        config: ProjectConfig,
        unit_id: str = "global",
        rows: Optional[int] = None,
        cols: Optional[int] = None,
        calibration: Optional[CalibrationConfig] = None,
    ) -> None:
        self.config = config
        self.unit_id = unit_id
        self.rows = rows if rows is not None else config.grid.rows
        self.cols = cols if cols is not None else config.grid.cols
        self._detection = config.detection

        self._classifier = ColorClassifier(config.classes, self._detection)
        self._warp_matrix: Optional[np.ndarray] = None
        self._warp_size: Tuple[int, int] = (config.camera.width, config.camera.height)

        cal = calibration if calibration is not None else config.calibration
        if cal.enabled:
            self._init_warp(cal)

        self._background_ref: Optional[BackgroundRef] = None
        self._load_background_ref()

        self._history: List[List[List[int]]] = [
            [[] for _ in range(self.cols)] for _ in range(self.rows)
        ]
        self._prev_grid: Dict[Tuple[int, int], int] = {}
        self._seq = 0
        self._last_frame: Optional[np.ndarray] = None

    def _load_background_ref(self) -> None:
        refs = load_background_refs()
        self._background_ref = refs.get(self.unit_id) or refs.get("global")

    def reload_background_ref(self) -> None:
        self._load_background_ref()

    def _init_warp(self, cal: CalibrationConfig) -> None:
        if len(cal.source_points) != 4 or len(cal.destination_points) != 4:
            return
        src = np.array(cal.source_points, dtype=np.float32)
        dst = np.array(cal.destination_points, dtype=np.float32)
        self._warp_matrix = cv2.getPerspectiveTransform(src, dst)
        self._warp_size = (cal.output_width, cal.output_height)

    def _ref_lab(self, r: int, c: int) -> Optional[np.ndarray]:
        if self._background_ref is None or not self._background_ref.cells:
            return None
        if r >= self._background_ref.rows or c >= self._background_ref.cols:
            return None
        cell = self._background_ref.cells[r][c]
        if len(cell) != 3:
            return None
        return np.array(cell, dtype=np.float64)

    def process_frame(self, frame: np.ndarray) -> FrameResult:
        self._seq += 1
        ts = int(time.time() * 1000)

        if self._warp_matrix is not None:
            frame = cv2.warpPerspective(frame, self._warp_matrix, self._warp_size)

        if self._detection.enabled:
            frame = preprocess_frame(frame, self._detection)

        self._last_frame = frame.copy()
        lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2Lab)

        cells: List[CellResult] = []
        changed: List[CellResult] = []

        for r in range(self.rows):
            for c in range(self.cols):
                if self._detection.enabled:
                    analysis = analyze_cell(
                        lab_frame, r, c, self.rows, self.cols,
                        self._detection, ref_lab=self._ref_lab(r, c),
                    )
                    if analysis.is_empty or not analysis.occupied:
                        class_id, label, confidence = EMPTY_CLASS_ID, EMPTY_LABEL, 1.0
                        occupied = False
                        mask_ratio = analysis.mask_area_ratio
                    else:
                        class_id, label, confidence = self._classifier.classify(analysis.lab_median)
                        occupied = True
                        mask_ratio = analysis.mask_area_ratio
                else:
                    h, w = lab_frame.shape[:2]
                    cell_h = h / self.rows
                    cell_w = w / self.cols
                    margin = self._detection.margin_ratio
                    y1 = int(r * cell_h + cell_h * margin)
                    y2 = int((r + 1) * cell_h - cell_h * margin)
                    x1 = int(c * cell_w + cell_w * margin)
                    x2 = int((c + 1) * cell_w - cell_w * margin)
                    roi = lab_frame[y1:y2, x1:x2]
                    if roi.size == 0:
                        continue
                    median_lab = np.median(roi.reshape(-1, 3), axis=0)
                    class_id, label, confidence = self._classifier.classify(median_lab)
                    occupied = class_id not in (EMPTY_CLASS_ID, -1)
                    mask_ratio = 1.0

                history = self._history[r][c]
                history.append(class_id)
                if len(history) > TEMPORAL_WINDOW:
                    history.pop(0)

                stable_id = max(set(history), key=history.count)
                stable_label = label if stable_id == class_id else self._label_for(stable_id)

                result = CellResult(
                    row=r, col=c,
                    class_id=stable_id,
                    label=stable_label,
                    confidence=round(confidence, 3),
                    occupied=occupied if stable_id != EMPTY_CLASS_ID else False,
                    mask_area_ratio=round(mask_ratio, 3),
                )
                cells.append(result)

                prev = self._prev_grid.get((r, c), -1)
                if stable_id != prev:
                    changed.append(result)
                    self._prev_grid[(r, c)] = stable_id

        debug_frame = self._last_frame if self._detection.debug_overlay else None
        merged = build_merged_preview(
            [MergedSlice("global", self._last_frame, 0, 0, self.rows, self.cols)]
            if self._last_frame is not None else [],
            self.rows,
            self.cols,
        )
        return FrameResult(
            seq=self._seq,
            timestamp_ms=ts,
            rows=self.rows,
            cols=self.cols,
            cells=cells,
            changed_cells=changed,
            debug_frame=debug_frame,
            merged_preview=merged,
        )

    def get_last_frame(self) -> Optional[np.ndarray]:
        return self._last_frame

    def _label_for(self, class_id: int) -> str:
        if class_id == EMPTY_CLASS_ID:
            return EMPTY_LABEL
        for cls_cfg in self.config.classes:
            if cls_cfg.class_id == class_id:
                return cls_cfg.label
        return "unknown"


class MultiTableDetector:
    """Manages multiple GridDetectors for a multi-table layout."""

    def __init__(self, config: ProjectConfig) -> None:
        self.config = config
        layout = config.layout
        self._unit_detectors: Dict[str, Tuple[GridDetector, cv2.VideoCapture, int, int]] = {}
        self._seq = 0
        self._prev_grid: Dict[Tuple[int, int], int] = {}

        total_rows = 0
        total_cols = 0
        for unit in layout.units:
            total_rows = max(total_rows, unit.grid_row_offset + unit.grid_rows)
            total_cols = max(total_cols, unit.grid_col_offset + unit.grid_cols)

            det = GridDetector(
                config,
                unit_id=unit.unit_id,
                rows=unit.grid_rows,
                cols=unit.grid_cols,
                calibration=unit.calibration,
            )

            cap = cv2.VideoCapture(unit.camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
            cap.set(cv2.CAP_PROP_FPS, config.camera.fps)

            self._unit_detectors[unit.unit_id] = (det, cap, unit.grid_row_offset, unit.grid_col_offset)

        self.total_rows = total_rows
        self.total_cols = total_cols

    def reload_background_refs(self) -> None:
        for uid, (det, _, _, _) in self._unit_detectors.items():
            det.reload_background_ref()

    def get_unit_detector(self, unit_id: str) -> Optional[GridDetector]:
        entry = self._unit_detectors.get(unit_id)
        return entry[0] if entry else None

    def process_all(self) -> FrameResult:
        self._seq += 1
        ts = int(time.time() * 1000)
        all_cells: List[CellResult] = []
        all_changed: List[CellResult] = []
        debug_frame: Optional[np.ndarray] = None
        slices: List[MergedSlice] = []

        for uid, (det, cap, row_off, col_off) in self._unit_detectors.items():
            ok, frame = cap.read()
            if not ok:
                continue
            local_result = det.process_frame(frame)
            if local_result.debug_frame is not None:
                debug_frame = local_result.debug_frame
            warped = det.get_last_frame()
            if warped is not None:
                slices.append(MergedSlice(
                    unit_id=uid,
                    frame=warped,
                    row_offset=row_off,
                    col_offset=col_off,
                    local_rows=det.rows,
                    local_cols=det.cols,
                ))
            for cell in local_result.cells:
                global_cell = CellResult(
                    row=cell.row + row_off, col=cell.col + col_off,
                    class_id=cell.class_id, label=cell.label, confidence=cell.confidence,
                    occupied=cell.occupied, mask_area_ratio=cell.mask_area_ratio,
                )
                all_cells.append(global_cell)
                prev = self._prev_grid.get((global_cell.row, global_cell.col), -1)
                if global_cell.class_id != prev:
                    all_changed.append(global_cell)
                    self._prev_grid[(global_cell.row, global_cell.col)] = global_cell.class_id

        merged = build_merged_preview(slices, self.total_rows, self.total_cols)
        return FrameResult(
            seq=self._seq, timestamp_ms=ts,
            rows=self.total_rows, cols=self.total_cols,
            cells=all_cells, changed_cells=all_changed,
            debug_frame=debug_frame,
            merged_preview=merged,
        )

    def release(self) -> None:
        for uid, (det, cap, _, _) in self._unit_detectors.items():
            cap.release()


def open_camera(config: ProjectConfig) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(config.camera.index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
    cap.set(cv2.CAP_PROP_FPS, config.camera.fps)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {config.camera.index}")
    return cap
