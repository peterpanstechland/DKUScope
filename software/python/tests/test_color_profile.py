from __future__ import annotations

import numpy as np
import pytest

from control_station.color_profile import (
    append_lab_sample,
    compute_profile_from_samples,
    ensure_class_color_profile,
    lab_in_range,
    profile_from_legacy_centroid,
)
from control_station.config_schema import BuildingClassConfig, DetectionConfig
from control_station.detection_service import ColorClassifier


def test_legacy_calibrated_lab_migration():
    cls = BuildingClassConfig(
        class_id=1, label="test", calibrated_lab=[50.0, 160.0, 140.0],
    )
    ensure_class_color_profile(cls)
    assert cls.lab_centroid == [50.0, 160.0, 140.0]
    assert len(cls.lab_min) == 3
    assert cls.lab_min[0] < cls.lab_max[0]


def test_samples_compute_min_max():
    samples = [[50, 155, 140], [52, 158, 138], [48, 152, 142]]
    centroid, std, lab_min, lab_max = compute_profile_from_samples(samples, l_padding=4, ab_padding=6)
    assert centroid[0] == pytest.approx(50.0, abs=1)
    assert lab_min[1] <= 152
    assert lab_max[1] >= 158


def test_append_sample_updates_profile():
    cls = BuildingClassConfig(class_id=1, label="test")
    append_lab_sample(cls, [50.0, 160.0, 140.0])
    append_lab_sample(cls, [54.0, 162.0, 138.0])
    assert len(cls.lab_samples) == 2
    assert cls.lab_centroid[0] == pytest.approx(52.0, abs=0.1)


def test_lab_in_range_box():
    lab = np.array([50.0, 160.0, 140.0])
    assert lab_in_range(lab, [42, 148, 128], [58, 172, 152])
    assert not lab_in_range(lab, [60, 170, 150], [70, 180, 160])


def test_color_classifier_box_match():
    cls = BuildingClassConfig(
        class_id=1, label="red", calibrated_lab=[50.0, 160.0, 140.0],
    )
    ensure_class_color_profile(cls)
    det = DetectionConfig(confidence_threshold=40.0)
    classifier = ColorClassifier([cls], det)
    cid, label, conf = classifier.classify(np.array([50.0, 160.0, 140.0]))
    assert cid == 1
    assert conf > 0.5


def test_profile_from_legacy_centroid():
    c, lab_min, lab_max = profile_from_legacy_centroid([100, 128, 128])
    assert c == [100.0, 128.0, 128.0]
    assert lab_min[0] == 92.0
    assert lab_max[0] == 108.0
