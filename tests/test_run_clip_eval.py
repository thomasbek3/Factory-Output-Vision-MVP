from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_clip_eval


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def write_calibration(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "source_polygons": [[(0, 0), (40, 0), (40, 100), (0, 100)]],
                "output_polygons": [[(60, 0), (100, 0), (100, 100), (60, 100)]],
                "ignore_polygons": [],
            }
        ),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_run_clip_eval_writes_summary_tracks_events_and_review_cards(tmp_path: Path) -> None:
    manifest_path = tmp_path / "frames.json"
    write_manifest(
        manifest_path,
        [
            {"frame_path": "f1.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.0, "width": 100, "height": 100},
            {"frame_path": "f2.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.1, "width": 100, "height": 100},
            {"frame_path": "f3.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.2, "width": 100, "height": 100},
            {"frame_path": "f4.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.3, "width": 100, "height": 100},
            {"frame_path": "f5.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.4, "width": 100, "height": 100},
            {"frame_path": "f6.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.5, "width": 100, "height": 100},
            {"frame_path": "f7.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.6, "width": 100, "height": 100},
            {"frame_path": "f8.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.7, "width": 100, "height": 100},
            {"frame_path": "f9.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.8, "width": 100, "height": 100},
        ],
    )
    calibration_path = tmp_path / "calibration.json"
    write_calibration(calibration_path)
    out_dir = tmp_path / "eval"
    detections_by_frame = [
        [{"box": (5, 20, 20, 20), "confidence": 0.9}],
        [{"box": (10, 20, 20, 20), "confidence": 0.9}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9}],
        # Reposition inside output under a new ID-ish jump. Should be resident/no count.
        [{"box": (72, 22, 20, 20), "confidence": 0.9}],
        # New true delivery from source.
        [{"box": (5, 50, 20, 20), "confidence": 0.9}],
        [{"box": (10, 50, 20, 20), "confidence": 0.9}],
        [{"box": (65, 50, 20, 20), "confidence": 0.9}],
        [{"box": (65, 50, 20, 20), "confidence": 0.9}],
    ]

    def fake_detector(*, frame, frame_index: int, frame_row: dict, model_path: Path | None, confidence: float):
        return detections_by_frame[frame_index - 1]

    result = run_clip_eval.run_clip_eval(
        manifest_path=manifest_path,
        calibration_path=calibration_path,
        out_dir=out_dir,
        model_path=None,
        confidence=0.25,
        force=False,
        detector_runner=fake_detector,
    )

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    events = read_jsonl(out_dir / "events.jsonl")
    tracks = read_jsonl(out_dir / "tracks.jsonl")

    assert result["total_count"] == 2
    assert summary["total_count"] == 2
    assert summary["frames_processed"] == 9
    assert [event["type"] for event in events] == ["count", "count"]
    assert events[0]["reason"] == "stable_in_output"
    assert len(tracks) == 9
    assert (out_dir / "review_cards" / "count-000001.json").exists()
    assert (out_dir / "review_cards" / "count-000002.json").exists()


def test_run_clip_eval_perception_gate_blocks_worker_overlap_before_count(tmp_path: Path) -> None:
    manifest_path = tmp_path / "frames.json"
    write_manifest(
        manifest_path,
        [
            {"frame_path": "f1.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.0, "width": 100, "height": 100},
            {"frame_path": "f2.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.1, "width": 100, "height": 100},
            {"frame_path": "f3.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.2, "width": 100, "height": 100},
            {"frame_path": "f4.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.3, "width": 100, "height": 100},
        ],
    )
    calibration_path = tmp_path / "calibration.json"
    write_calibration(calibration_path)
    out_dir = tmp_path / "eval"
    detections_by_frame = [
        [{"box": (5, 20, 20, 20), "confidence": 0.9, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0}],
        [{"box": (10, 20, 20, 20), "confidence": 0.9, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0}],
    ]

    def fake_detector(*, frame, frame_index: int, frame_row: dict, model_path: Path | None, confidence: float):
        return detections_by_frame[frame_index - 1]

    result = run_clip_eval.run_clip_eval(
        manifest_path=manifest_path,
        calibration_path=calibration_path,
        out_dir=out_dir,
        model_path=None,
        confidence=0.25,
        force=False,
        detector_runner=fake_detector,
        tracker_match_distance=100.0,
        enable_perception_gate=True,
    )

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    tracks = read_jsonl(out_dir / "tracks.jsonl")

    assert result["total_count"] == 0
    assert summary["perception_gate_summary"]["decision_counts"]["reject"] == 1
    assert summary["perception_gate_summary"]["reason_counts"] == {"worker_body_overlap": 1}
    assert tracks[0]["tracks"][0]["perception_gate"]["decision"] == "reject"
    assert not (out_dir / "events.jsonl").exists()


def test_run_clip_eval_perception_gate_uses_person_detector_overlap(tmp_path: Path) -> None:
    manifest_path = tmp_path / "frames.json"
    write_manifest(
        manifest_path,
        [
            {"frame_path": "f1.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.0, "width": 100, "height": 100},
            {"frame_path": "f2.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.1, "width": 100, "height": 100},
            {"frame_path": "f3.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.2, "width": 100, "height": 100},
            {"frame_path": "f4.jpg", "video_path": "clip.mp4", "timestamp_seconds": 0.3, "width": 100, "height": 100},
        ],
    )
    calibration_path = tmp_path / "calibration.json"
    write_calibration(calibration_path)
    out_dir = tmp_path / "eval-person"
    detections_by_frame = [
        [{"box": (5, 20, 20, 20), "confidence": 0.9}],
        [{"box": (10, 20, 20, 20), "confidence": 0.9}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9}],
        [{"box": (65, 20, 20, 20), "confidence": 0.9}],
    ]

    def fake_detector(*, frame, frame_index: int, frame_row: dict, model_path: Path | None, confidence: float):
        return detections_by_frame[frame_index - 1]

    def fake_person_detector(*, frame, frame_index: int, frame_row: dict, model_path: Path | None, confidence: float):
        return [(0, 0, 100, 100)]

    result = run_clip_eval.run_clip_eval(
        manifest_path=manifest_path,
        calibration_path=calibration_path,
        out_dir=out_dir,
        model_path=None,
        confidence=0.25,
        force=False,
        detector_runner=fake_detector,
        person_detector_runner=fake_person_detector,
        tracker_match_distance=100.0,
        enable_perception_gate=True,
    )

    tracks = read_jsonl(out_dir / "tracks.jsonl")

    assert result["total_count"] == 0
    assert tracks[0]["tracks"][0]["perception_gate"]["reason"] == "worker_body_overlap"


def test_run_clip_eval_refuses_existing_out_dir_without_force(tmp_path: Path) -> None:
    manifest_path = tmp_path / "frames.json"
    write_manifest(manifest_path, [])
    calibration_path = tmp_path / "calibration.json"
    write_calibration(calibration_path)
    out_dir = tmp_path / "eval"
    out_dir.mkdir()
    (out_dir / "summary.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--force"):
        run_clip_eval.run_clip_eval(
            manifest_path=manifest_path,
            calibration_path=calibration_path,
            out_dir=out_dir,
            model_path=None,
            confidence=0.25,
            force=False,
            detector_runner=lambda **kwargs: [],
        )


def test_load_calibration_rejects_missing_source_or_output(tmp_path: Path) -> None:
    calibration_path = tmp_path / "bad.json"
    calibration_path.write_text(json.dumps({"source_polygons": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="source_polygons.*output_polygons"):
        run_clip_eval.load_calibration(calibration_path)


def test_run_clip_eval_script_help_works_when_invoked_by_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "scripts/run_clip_eval.py", "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Run Factory Vision clip-level event evaluation" in result.stdout
