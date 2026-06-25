from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from .config_schema import BuildingClassConfig

DEFAULT_L_PADDING = 8.0
DEFAULT_AB_PADDING = 12.0


def normalize_lab_samples(samples: List[List[float]]) -> List[List[float]]:
    out: List[List[float]] = []
    for s in samples:
        if len(s) == 3:
            out.append([float(s[0]), float(s[1]), float(s[2])])
    return out


def compute_profile_from_samples(
    samples: List[List[float]],
    l_padding: float = DEFAULT_L_PADDING,
    ab_padding: float = DEFAULT_AB_PADDING,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Return centroid, std, lab_min, lab_max from sample list."""
    if not samples:
        return [], [], [], []

    arr = np.array(normalize_lab_samples(samples), dtype=np.float64)
    centroid = np.mean(arr, axis=0).tolist()
    std = np.std(arr, axis=0).tolist() if len(arr) > 1 else [0.0, 0.0, 0.0]
    mins = np.min(arr, axis=0)
    maxs = np.max(arr, axis=0)
    lab_min = [
        float(mins[0] - l_padding),
        float(mins[1] - ab_padding),
        float(mins[2] - ab_padding),
    ]
    lab_max = [
        float(maxs[0] + l_padding),
        float(maxs[1] + ab_padding),
        float(maxs[2] + ab_padding),
    ]
    return centroid, std, lab_min, lab_max


def profile_from_legacy_centroid(
    centroid: List[float],
    l_padding: float = DEFAULT_L_PADDING,
    ab_padding: float = DEFAULT_AB_PADDING,
) -> Tuple[List[float], List[float], List[float]]:
    if len(centroid) != 3:
        return [], [], []
    c = [float(centroid[0]), float(centroid[1]), float(centroid[2])]
    lab_min = [c[0] - l_padding, c[1] - ab_padding, c[2] - ab_padding]
    lab_max = [c[0] + l_padding, c[1] + ab_padding, c[2] + ab_padding]
    return c, lab_min, lab_max


def ensure_class_color_profile(
    cls: BuildingClassConfig,
    l_padding: float = DEFAULT_L_PADDING,
    ab_padding: float = DEFAULT_AB_PADDING,
) -> BuildingClassConfig:
    """Fill centroid/min/max from samples or legacy calibrated_lab."""
    samples = normalize_lab_samples(cls.lab_samples)
    if samples:
        centroid, std, lab_min, lab_max = compute_profile_from_samples(
            samples, l_padding=l_padding, ab_padding=ab_padding,
        )
        cls.lab_centroid = centroid
        cls.lab_std = std
        cls.lab_min = lab_min
        cls.lab_max = lab_max
        cls.calibrated_lab = centroid
        return cls

    if cls.lab_centroid and len(cls.lab_centroid) == 3:
        centroid = cls.lab_centroid
    elif cls.calibrated_lab and len(cls.calibrated_lab) == 3:
        centroid = cls.calibrated_lab
    else:
        return cls

    c, lab_min, lab_max = profile_from_legacy_centroid(centroid, l_padding, ab_padding)
    cls.lab_centroid = c
    cls.lab_min = lab_min
    cls.lab_max = lab_max
    cls.calibrated_lab = c
    return cls


def append_lab_sample(
    cls: BuildingClassConfig,
    lab: List[float],
    l_padding: float = DEFAULT_L_PADDING,
    ab_padding: float = DEFAULT_AB_PADDING,
) -> BuildingClassConfig:
    if len(lab) != 3:
        return cls
    samples = normalize_lab_samples(cls.lab_samples)
    samples.append([float(lab[0]), float(lab[1]), float(lab[2])])
    cls.lab_samples = samples
    return ensure_class_color_profile(cls, l_padding=l_padding, ab_padding=ab_padding)


def lab_in_range(lab: np.ndarray, lab_min: List[float], lab_max: List[float]) -> bool:
    if len(lab_min) != 3 or len(lab_max) != 3:
        return False
    return bool(
        lab_min[0] <= lab[0] <= lab_max[0]
        and lab_min[1] <= lab[1] <= lab_max[1]
        and lab_min[2] <= lab[2] <= lab_max[2]
    )


def range_diagonal(lab_min: List[float], lab_max: List[float]) -> float:
    if len(lab_min) != 3 or len(lab_max) != 3:
        return 200.0
    d = np.array(lab_max, dtype=np.float64) - np.array(lab_min, dtype=np.float64)
    return float(max(np.linalg.norm(d), 1.0))
