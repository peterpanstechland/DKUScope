from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config_schema import BuildingClassConfig, CalibrationConfig, ProjectConfig


CONFIDENCE_THRESHOLD = 40.0
TEMPORAL_WINDOW = 3


@dataclass
class CellResult:
    row: int
    col: int
    class_id: int
    label: str
    confidence: float


@dataclass
class FrameResult:
    seq: int
    timestamp_ms: int
    rows: int
    cols: int
    cells: List[CellResult]
    changed_cells: List[CellResult] = field(default_factory=list)


class ColorClassifier:
    def __init__(self, classes: List[BuildingClassConfig]) -> None:
        self._centroids: List[Tuple[int, np.ndarray, str]] = []
        for cls_cfg in classes:
            if cls_cfg.calibrated_lab and len(cls_cfg.calibrated_lab) == 3:
                self._centroids.append((
                    cls_cfg.class_id,
                    np.array(cls_cfg.calibrated_lab, dtype=np.float64),
                    cls_cfg.label,
                ))
        if not self._centroids:
            raise ValueError(
                "No classes have calibrated Lab values. "
                "Use the control station to sample colors first."
            )

    def classify(self, lab_median: np.ndarray) -> Tuple[int, str, float]:
        best_id = -1
        best_label = "unknown"
        best_dist = float("inf")
        for class_id, centroid, label in self._centroids:
            dist = float(np.linalg.norm(lab_median - centroid))
            if dist < best_dist:
                best_dist = dist
                best_id = class_id
                best_label = label
        confidence = max(0.0, 1.0 - best_dist / 200.0)
        if best_dist > CONFIDENCE_THRESHOLD:
            return -1, "unknown", confidence
        return best_id, best_label, confidence


class GridDetector:
    def __init__(self, config: ProjectConfig) -> None:
        self.config = config
        self.rows = config.grid.rows
        self.cols = config.grid.cols

        self._classifier = ColorClassifier(config.classes)
        self._warp_matrix: Optional[np.ndarray] = None
        self._warp_size: Tuple[int, int] = (config.camera.width, config.camera.height)

        if config.calibration.enabled:
            self._init_warp(config.calibration)

        self._history: List[List[List[int]]] = [
            [[] for _ in range(self.cols)] for _ in range(self.rows)
        ]
        self._prev_grid: Dict[Tuple[int, int], int] = {}
        self._seq = 0

    def _init_warp(self, cal: CalibrationConfig) -> None:
        if len(cal.source_points) != 4 or len(cal.destination_points) != 4:
            return
        src = np.array(cal.source_points, dtype=np.float32)
        dst = np.array(cal.destination_points, dtype=np.float32)
        self._warp_matrix = cv2.getPerspectiveTransform(src, dst)
        self._warp_size = (cal.output_width, cal.output_height)

    def process_frame(self, frame: np.ndarray) -> FrameResult:
        self._seq += 1
        ts = int(time.time() * 1000)

        if self._warp_matrix is not None:
            frame = cv2.warpPerspective(frame, self._warp_matrix, self._warp_size)

        lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2Lab)
        h, w = lab_frame.shape[:2]
        cell_h = h / self.rows
        cell_w = w / self.cols

        margin_ratio = 0.15
        cells: List[CellResult] = []
        changed: List[CellResult] = []

        for r in range(self.rows):
            for c in range(self.cols):
                y1 = int(r * cell_h + cell_h * margin_ratio)
                y2 = int((r + 1) * cell_h - cell_h * margin_ratio)
                x1 = int(c * cell_w + cell_w * margin_ratio)
                x2 = int((c + 1) * cell_w - cell_w * margin_ratio)

                roi = lab_frame[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                median_lab = np.median(roi.reshape(-1, 3), axis=0)
                class_id, label, confidence = self._classifier.classify(median_lab)

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
                )
                cells.append(result)

                prev = self._prev_grid.get((r, c), -1)
                if stable_id != prev:
                    changed.append(result)
                    self._prev_grid[(r, c)] = stable_id

        return FrameResult(
            seq=self._seq,
            timestamp_ms=ts,
            rows=self.rows,
            cols=self.cols,
            cells=cells,
            changed_cells=changed,
        )

    def _label_for(self, class_id: int) -> str:
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
        self._classifier = ColorClassifier(config.classes)
        self._seq = 0
        self._prev_grid: Dict[Tuple[int, int], int] = {}

        total_rows = 0
        total_cols = 0
        for unit in layout.units:
            total_rows = max(total_rows, unit.grid_row_offset + unit.grid_rows)
            total_cols = max(total_cols, unit.grid_col_offset + unit.grid_cols)

            det = GridDetector.__new__(GridDetector)
            det.config = config
            det.rows = unit.grid_rows
            det.cols = unit.grid_cols
            det._classifier = self._classifier
            det._warp_matrix = None
            det._warp_size = (config.camera.width, config.camera.height)
            if unit.calibration.enabled:
                det._init_warp(unit.calibration)
            det._history = [[[] for _ in range(det.cols)] for _ in range(det.rows)]
            det._prev_grid = {}
            det._seq = 0

            cap = cv2.VideoCapture(unit.camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
            cap.set(cv2.CAP_PROP_FPS, config.camera.fps)

            self._unit_detectors[unit.unit_id] = (det, cap, unit.grid_row_offset, unit.grid_col_offset)

        self.total_rows = total_rows
        self.total_cols = total_cols

    def process_all(self) -> FrameResult:
        self._seq += 1
        ts = int(time.time() * 1000)
        all_cells: List[CellResult] = []
        all_changed: List[CellResult] = []

        for uid, (det, cap, row_off, col_off) in self._unit_detectors.items():
            ok, frame = cap.read()
            if not ok:
                continue
            local_result = det.process_frame(frame)
            for cell in local_result.cells:
                global_cell = CellResult(
                    row=cell.row + row_off, col=cell.col + col_off,
                    class_id=cell.class_id, label=cell.label, confidence=cell.confidence,
                )
                all_cells.append(global_cell)
                prev = self._prev_grid.get((global_cell.row, global_cell.col), -1)
                if global_cell.class_id != prev:
                    all_changed.append(global_cell)
                    self._prev_grid[(global_cell.row, global_cell.col)] = global_cell.class_id

        return FrameResult(
            seq=self._seq, timestamp_ms=ts,
            rows=self.total_rows, cols=self.total_cols,
            cells=all_cells, changed_cells=all_changed,
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
