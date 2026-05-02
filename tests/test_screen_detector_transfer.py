from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.screen_detector_transfer import screen_detector, uniform_timestamps


class FakeDetector:
    def __init__(self, frame_confidences: list[list[float]]) -> None:
        self.frame_confidences = frame_confidences
        self.calls = 0

    def predict(self, source, conf: float, verbose: bool):  # noqa: ANN001
        values = self.frame_confidences[self.calls]
        self.calls += 1
        return [SimpleNamespace(boxes=SimpleNamespace(conf=values))]


def test_uniform_timestamps_use_midpoints() -> None:
    assert uniform_timestamps(100.0, 4) == [12.5, 37.5, 62.5, 87.5]


def test_uniform_timestamps_reject_bad_inputs() -> None:
    with pytest.raises(ValueError, match="sample_count"):
        uniform_timestamps(100.0, 0)
    with pytest.raises(ValueError, match="duration_sec"):
        uniform_timestamps(0.0, 4)


def test_screen_detector_flags_transfer_failure() -> None:
    payload = screen_detector(
        detector=FakeDetector([[], [], [], []]),
        model_path=Path("models/weak.pt"),
        frames=[object(), object(), object(), object()],
        confidences=[0.25],
    )

    summary = payload["confidence_summaries"][0]
    assert summary["images_with_detections"] == 0
    assert summary["detection_rate"] == 0.0
    assert summary["recommendation"] == "transfer_failed_build_video_specific_detector"


def test_screen_detector_flags_broad_static_risk() -> None:
    payload = screen_detector(
        detector=FakeDetector([[0.9], [0.8], [0.7], [0.6]]),
        model_path=Path("models/broad.pt"),
        frames=[object(), object(), object(), object()],
        confidences=[0.25],
    )

    assert payload["confidence_summaries"][0]["recommendation"] == (
        "broad_or_static_detector_risk_requires_runtime_diagnostic"
    )
