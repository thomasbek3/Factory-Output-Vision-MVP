from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from scripts import benchmark_ai_onboarding as bench


def test_teacher_consensus_requires_multiple_agreeing_teachers() -> None:
    windows = [
        {
            "window_id": "window-000001",
            "time_window": {"center_sec": 10.0},
            "frame_asset": {"frame_path": "frame.jpg"},
        }
    ]

    def fake_teacher(*, teacher_id: str, window: dict) -> dict:
        return {
            "teacher_id": teacher_id,
            "window_id": window["window_id"],
            "event_type": "completed_output_placement",
            "countable": True,
            "event_ts": 10.2 if teacher_id.endswith("-1") else 10.7,
            "box_xyxy": [10, 20, 40, 60],
            "confidence": 0.91,
            "rationale": "visible completed placement",
        }

    labels = bench.build_teacher_labels(
        windows=windows,
        teacher_provider="fixture",
        teacher_count=2,
        teacher_runner=fake_teacher,
    )
    consensus = bench.build_consensus(
        teacher_labels=labels,
        min_teacher_agreement=2,
        min_confidence=0.75,
        timestamp_tolerance_sec=1.0,
    )

    assert labels["refuses_validation_truth"] is True
    assert all(label["validation_truth_eligible"] is False for label in labels["labels"])
    assert consensus["consensus_event_count"] == 1
    assert consensus["events"][0]["teacher_agreement"] == 2
    assert consensus["events"][0]["validation_truth_eligible"] is False
    assert consensus["events"][0]["training_eligible"] is True


def test_holdout_grade_can_redact_expected_total() -> None:
    grade = bench.build_holdout_grade(
        expected_total=999,
        consensus_count=12,
        tolerance=1,
        redact=True,
    )

    assert grade == {
        "status": "graded",
        "expected_total_redacted": True,
        "within_tolerance": False,
        "tolerance": 1,
    }


def test_run_benchmark_keeps_holdout_truth_out_of_onboarding_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "frame.jpg"
    cv2.imwrite(str(image_path), np.zeros((100, 120, 3), dtype=np.uint8))
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"not-a-real-video-because-extraction-is-stubbed")

    monkeypatch.setattr(
        bench,
        "probe_video",
        lambda video_path: {
            "path": str(video_path),
            "sha256": "abc",
            "fps": 10.0,
            "frame_count": 100,
            "duration_sec": 10.0,
            "width": 120,
            "height": 100,
        },
    )
    monkeypatch.setattr(
        bench,
        "extract_sample_frames",
        lambda **kwargs: [
            {
                "frame_id": "frame-000001",
                "frame_path": image_path.as_posix(),
                "timestamp_sec": 3.0,
                "sha256": "framehash",
                "width": 120,
                "height": 100,
            }
        ],
    )

    def fake_teacher(*, teacher_id: str, window: dict) -> dict:
        return {
            "teacher_id": teacher_id,
            "window_id": window["window_id"],
            "event_type": "completed_output_placement",
            "countable": True,
            "event_ts": 3.0,
            "box_xyxy": [12, 20, 52, 60],
            "confidence": 0.9,
            "rationale": "fixture consensus",
        }

    output = tmp_path / "report.json"
    report = bench.run_benchmark(
        video_path=video_path,
        station_id="fixture-station",
        minutes=1,
        output=output,
        work_dir=tmp_path / "work",
        teacher_provider="fixture",
        teacher_count=3,
        min_teacher_agreement=2,
        min_confidence=0.75,
        timestamp_tolerance_sec=2.0,
        sample_interval_sec=10,
        max_frames=10,
        candidate_model=None,
        detector_confidence=0.25,
        held_out_expected_total=999,
        holdout_tolerance=1,
        redact_held_out_truth=True,
        force=True,
        teacher_runner=fake_teacher,
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    teacher_labels = json.loads(Path(report["paths"]["teacher_labels"]).read_text(encoding="utf-8"))
    consensus = json.loads(Path(report["paths"]["consensus"]).read_text(encoding="utf-8"))

    assert written["blind_boundary"]["held_out_truth_used_by_onboarding"] is False
    assert written["held_out_grade"]["expected_total_redacted"] is True
    assert "expected_total" not in written["held_out_grade"]
    assert teacher_labels["refuses_validation_truth"] is True
    assert "expected_total" not in json.dumps(teacher_labels)
    assert "expected_total" not in json.dumps(consensus)
    assert written["consensus_summary"]["consensus_event_count"] == 1
    assert written["dataset"]["ready_for_training"] is True
