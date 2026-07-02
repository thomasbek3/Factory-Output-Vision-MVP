from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.clip_models import train_student, write_synthetic_clip_manifest
from app.services.zone_tripwire import TripwireConfig
from scripts import run_clip_exam


def test_run_clip_exam_cli_extracts_tripwire_candidates_and_counts(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "placement.mp4"
    write_video(video, placement_frames(), fps=10)
    calibration = tmp_path / "station_calibration.json"
    calibration.write_text(
        json.dumps({"output_polygons": [[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]]]}),
        encoding="utf-8",
    )
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"events": [{"id": "placement-1", "clip_offset_sec": 1.0}]}), encoding="utf-8")
    model_path = train_asserting_stack3_student(tmp_path)
    out_path = tmp_path / "exam.json"

    monkeypatch.setattr(
        run_clip_exam,
        "TripwireConfig",
        lambda: TripwireConfig(
            trigger="pixel",
            sample_fps=10,
            burst_threshold=0.95,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.2,
            min_flash_ratio=0.1,
            bracket_sec=1.0,
        ),
    )

    exit_code = run_clip_exam.main(
        [
            "--video",
            str(video),
            "--gold-positives",
            str(gold),
            "--station-calibration",
            str(calibration),
            "--model",
            str(model_path),
            "--arch",
            "stack3_mobilenet",
            "--debounce-sec",
            "0.5",
            "--match-tolerance-sec",
            "1.0",
            "--out",
            str(out_path),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["candidate_count"] >= 1
    assert payload["counts"]
    assert payload["count_times"]
    assert payload["matched"] == 1
    assert payload["false_counts"] == 0
    assert payload["passed"] is True


def train_asserting_stack3_student(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "train_manifest.json"
    write_synthetic_clip_manifest(manifest_path, sample_count=4, image_size=32)
    result = train_student(
        manifest_path=manifest_path,
        arch="stack3_mobilenet",
        out_dir=tmp_path / "models",
        epochs=1,
        batch_size=2,
        device="cpu",
        pretrained=False,
    )
    assert result["status"] == "trained"
    model_path = Path(result["model_path"])

    import torch

    checkpoint = torch.load(model_path, map_location="cpu")
    state = checkpoint["state_dict"]
    state["classifier.3.weight"].zero_()
    state["classifier.3.bias"] = torch.tensor([-10.0, 10.0])
    torch.save(checkpoint, model_path)
    return model_path


def placement_frames() -> list[np.ndarray]:
    frames = []
    for index in range(24):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        if index >= 10:
            frame[48:56, 48:60] = 255
        frames.append(frame)
    return frames


def write_video(path: Path, frames: list[np.ndarray], *, fps: int) -> None:
    import cv2  # type: ignore

    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()
    assert path.exists()
