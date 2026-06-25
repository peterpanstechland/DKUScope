from __future__ import annotations

import numpy as np
import pytest

from control_station.color_profile import (
    append_lab_sample,
    append_lab_samples,
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
    assert len(cls.lab_samples) == 1
    assert cls.lab_samples[0] == [50.0, 160.0, 140.0]


def test_legacy_centroid_without_samples_migrates_on_load():
    cls = BuildingClassConfig(
        class_id=3,
        label="test",
        lab_centroid=[197.0, 131.0, 206.0],
        lab_min=[189.0, 119.0, 194.0],
        lab_max=[205.0, 143.0, 218.0],
        calibrated_lab=[197.0, 131.0, 206.0],
    )
    ensure_class_color_profile(cls)
    assert len(cls.lab_samples) == 1
    assert cls.lab_samples[0][0] == pytest.approx(197.0, abs=0.1)


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


def test_append_lab_samples_batch():
    cls = BuildingClassConfig(class_id=1, label="test")
    append_lab_samples(cls, [[50.0, 160.0, 140.0], [54.0, 162.0, 138.0], [48.0, 158.0, 142.0]])
    assert len(cls.lab_samples) == 3


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


def test_pink_not_classified_as_light_blue():
    pink = BuildingClassConfig(
        class_id=5,
        label="pink",
        lab_samples=[[193, 164, 123], [190, 162, 125], [195, 166, 121]],
    )
    blue = BuildingClassConfig(
        class_id=7,
        label="blue",
        lab_samples=[[202, 113, 107], [198, 115, 110]],
    )
    ensure_class_color_profile(pink)
    ensure_class_color_profile(blue)
    det = DetectionConfig(confidence_threshold=40.0, color_match_l_weight=0.35)
    classifier = ColorClassifier([pink, blue], det)

    cid, label, _ = classifier.classify(np.array([193.0, 164.0, 123.0]))
    assert cid == 5

    cid, label, _ = classifier.classify(np.array([175.0, 155.0, 115.0]))
    assert cid == 5, f"shadow pink misclassified as {label}"

    cid, label, _ = classifier.classify(np.array([202.0, 113.0, 107.0]))
    assert cid == 7


def test_profile_from_legacy_centroid():
    c, lab_min, lab_max = profile_from_legacy_centroid([100, 128, 128])
    assert c == [100.0, 128.0, 128.0]
    assert lab_min[0] == 92.0
    assert lab_max[0] == 108.0
