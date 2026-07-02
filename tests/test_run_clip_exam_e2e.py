from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.clip_models import train_student, write_synthetic_clip_manifest
from app.services.zone_tripwire import TripwireConfig
from scripts import run_clip_exam


def test_run_clip_exam_cli_extracts_tripwire_candidates_and_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch_tripwire_config(monkeypatch)
    paths = write_exam_inputs(tmp_path)
    model_path = train_asserting_stack3_student(tmp_path)
    out_path = tmp_path / "exam.json"

    exit_code = run_exam_cli(paths=paths, model_path=model_path, out_path=out_path)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["candidate_count"] >= 1
    assert payload["counts"]
    assert payload["count_times"]
    assert payload["matched"] == 1
    assert payload["false_counts"] == 0
    assert payload["passed"] is True


def test_run_clip_exam_can_write_and_reuse_tripwire_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch_tripwire_config(monkeypatch)
    paths = write_exam_inputs(tmp_path)
    model_path = train_asserting_stack3_student(tmp_path)
    first_out_path = tmp_path / "exam_first.json"
    second_out_path = tmp_path / "exam_second.json"
    candidates_path = tmp_path / "tripwire_candidates.json"

    first_exit_code = run_exam_cli(
        paths=paths,
        model_path=model_path,
        out_path=first_out_path,
        extra_args=["--write-candidates", str(candidates_path)],
    )
    first_payload = json.loads(first_out_path.read_text(encoding="utf-8"))
    candidates_payload = json.loads(candidates_path.read_text(encoding="utf-8"))

    assert first_exit_code == 0
    assert candidates_payload["schema"] == run_clip_exam.TRIPWIRE_CANDIDATES_SCHEMA

    def fail_tripwire(*args, **kwargs):
        raise AssertionError("cached exam run must not invoke tripwire")

    monkeypatch.setattr(run_clip_exam, "run_tripwire_on_video", fail_tripwire)

    second_exit_code = run_exam_cli(
        paths=paths,
        model_path=model_path,
        out_path=second_out_path,
        extra_args=["--candidates", str(candidates_path)],
    )
    second_payload = json.loads(second_out_path.read_text(encoding="utf-8"))

    assert second_exit_code == 0
    assert second_payload["candidate_count"] == first_payload["candidate_count"]
    assert second_payload["counts"] == first_payload["counts"]
    assert second_payload["count_times"] == first_payload["count_times"]
    assert second_payload["matched"] == first_payload["matched"]
    assert second_payload["missed"] == first_payload["missed"]
    assert second_payload["false_counts"] == first_payload["false_counts"]
    assert second_payload["passed"] == first_payload["passed"]


def test_run_clip_exam_rejects_wrong_candidates_schema(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch_tripwire_config(monkeypatch)
    paths = write_exam_inputs(tmp_path)
    model_path = train_asserting_stack3_student(tmp_path)
    bad_candidates_path = tmp_path / "bad_candidates.json"
    bad_candidates_path.write_text(json.dumps({"schema": "wrong", "candidates": []}), encoding="utf-8")

    exit_code = run_exam_cli(
        paths=paths,
        model_path=model_path,
        out_path=tmp_path / "exam.json",
        extra_args=["--candidates", str(bad_candidates_path)],
    )

    captured = capsys.readouterr()
    assert exit_code == run_clip_exam.STAGE_EXIT_CODES["candidates"]
    assert "candidates stage failed" in captured.err
    assert "tripwire-candidates-v1" in captured.err


def monkeypatch_tripwire_config(monkeypatch) -> None:
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


def write_exam_inputs(tmp_path: Path) -> dict[str, Path]:
    video = tmp_path / "placement.mp4"
    write_video(video, placement_frames(), fps=10)
    calibration = tmp_path / "station_calibration.json"
    calibration.write_text(
        json.dumps({"output_polygons": [[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]]]}),
        encoding="utf-8",
    )
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"events": [{"id": "placement-1", "clip_offset_sec": 1.0}]}), encoding="utf-8")
    return {"video": video, "calibration": calibration, "gold": gold}


def run_exam_cli(*, paths: dict[str, Path], model_path: Path, out_path: Path, extra_args: list[str] | None = None) -> int:
    return run_clip_exam.main(
        [
            "--video",
            str(paths["video"]),
            "--gold-positives",
            str(paths["gold"]),
            "--station-calibration",
            str(paths["calibration"]),
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
            *(extra_args or []),
        ],
    )


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
