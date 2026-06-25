from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .paths import get_install_dir


@dataclass
class BackgroundRef:
    rows: int = 0
    cols: int = 0
    cells: List[List[List[float]]] = field(default_factory=list)

    def to_array(self) -> Optional[np.ndarray]:
        if not self.cells or self.rows <= 0 or self.cols <= 0:
            return None
        return np.array(self.cells, dtype=np.float64)


def get_background_refs_path() -> Path:
    return get_install_dir() / "config" / "background_refs.json"


def load_background_refs(path: Optional[Path] = None) -> Dict[str, BackgroundRef]:
    resolved = path or get_background_refs_path()
    if not resolved.exists():
        return {}
    with resolved.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, BackgroundRef] = {}
    for key, val in raw.items():
        out[key] = BackgroundRef(
            rows=int(val.get("rows", 0)),
            cols=int(val.get("cols", 0)),
            cells=val.get("cells", []),
        )
    return out


def save_background_refs(refs: Dict[str, BackgroundRef], path: Optional[Path] = None) -> Path:
    resolved = path or get_background_refs_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: {"rows": ref.rows, "cols": ref.cols, "cells": ref.cells}
        for key, ref in refs.items()
    }
    with resolved.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return resolved


def capture_background_from_lab_grid(
    lab_frame: np.ndarray,
    rows: int,
    cols: int,
    margin_ratio: float = 0.15,
) -> BackgroundRef:
    h, w = lab_frame.shape[:2]
    cell_h = h / rows
    cell_w = w / cols
    cells: List[List[List[float]]] = []
    for r in range(rows):
        row_vals: List[List[float]] = []
        for c in range(cols):
            y1 = int(r * cell_h + cell_h * margin_ratio)
            y2 = int((r + 1) * cell_h - cell_h * margin_ratio)
            x1 = int(c * cell_w + cell_w * margin_ratio)
            x2 = int((c + 1) * cell_w - cell_w * margin_ratio)
            roi = lab_frame[y1:y2, x1:x2]
            if roi.size == 0:
                row_vals.append([0.0, 128.0, 128.0])
            else:
                med = np.median(roi.reshape(-1, 3), axis=0)
                row_vals.append([float(med[0]), float(med[1]), float(med[2])])
        cells.append(row_vals)
    return BackgroundRef(rows=rows, cols=cols, cells=cells)
