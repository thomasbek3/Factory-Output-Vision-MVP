from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.zone_tripwire import TripwireConfig, run_tripwire_on_video, tiled_change_score, whole_zone_absdiff
from scripts.validate_tripwire_recall import build_tripwire_recall_report


def test_tiled_absdiff_sees_thin_bar_that_whole_zone_mean_hides() -> None:
    before = np.zeros((80, 80), dtype=np.uint8)
    after = before.copy()
    after[0:10, 0:10] = 255
    after[10:20, 10:20] = 255
    after[20:30, 20:30] = 255

    tiled = tiled_change_score(before, after, grid_size=8, method="tiled_absdiff")
    whole = whole_zone_absdiff(before, after)

    assert tiled == 1.0
    assert whole < 0.05


def test_quiet_state_diff_fires_after_calm_before_after_pair(tmp_path: Path) -> None:
    video = tmp_path / "quiet.mp4"
    frames = []
    for index in range(30):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        if index >= 10:
            frame[40:44, 40:60] = 255
        frames.append(frame)
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            sample_fps=10,
            burst_threshold=0.95,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.2,
            min_flash_ratio=0.1,
            bracket_sec=1.0,
        ),
    )

    assert any(row["trigger_mode"] == "quiet_state_diff" for row in payload["candidates"])


def test_uniform_flash_is_rejected(tmp_path: Path) -> None:
    video = tmp_path / "flash.mp4"
    frames = []
    for index in range(20):
        value = 0 if index < 5 else 128
        frames.append(np.full((64, 64, 3), value, dtype=np.uint8))
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            sample_fps=10,
            burst_threshold=0.1,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.1,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    assert payload["candidates"] == []
    assert payload["summary"]["dropped_flash_count"] > 0


def test_local_zone_placement_survives_large_outside_bench_motion(tmp_path: Path) -> None:
    video = tmp_path / "placement-plus-bench-motion.mp4"
    frames = []
    for index in range(20):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        if index >= 5:
            frame[:, :24] = 255
            frame[48:56, 48:56] = 255
        frames.append(frame)
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            sample_fps=10,
            burst_threshold=0.5,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.5,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    assert any(row["trigger_mode"] == "motion_burst" for row in payload["candidates"])


def test_run_tripwire_samples_frames_at_approximately_target_fps(tmp_path: Path) -> None:
    video = tmp_path / "sampling.mp4"
    frames = []
    for index in range(30):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :] = index
        frames.append(frame)
    write_video(video, frames, fps=30)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]],
        config=TripwireConfig(
            sample_fps=10,
            burst_threshold=1.0,
            state_interval_sec=0.5,
            calm_threshold=0.0,
            state_threshold=1.0,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    sampled_frame_count = payload["summary"]["sample_count"] + 1
    assert 9 <= sampled_frame_count <= 11


def test_tripwire_recall_gate_passes_at_six_of_seven_and_fails_at_five() -> None:
    gold = [{"id": f"gold-{index}", "time": float(index * 100)} for index in range(7)]

    pass_report = build_tripwire_recall_report(
        candidates=[{"candidate_id": f"c-{index}", "time": float(index * 100)} for index in range(6)],
        gold=gold,
        match_tolerance_sec=20,
    )
    fail_report = build_tripwire_recall_report(
        candidates=[{"candidate_id": f"c-{index}", "time": float(index * 100)} for index in range(5)],
        gold=gold,
        match_tolerance_sec=20,
    )

    assert pass_report["summary"]["caught"] == 6
    assert pass_report["verdict"] == "PASS"
    assert fail_report["summary"]["caught"] == 5
    assert fail_report["verdict"] == "FAIL"


def test_run_zone_tripwire_script_help() -> None:
    path = Path("scripts/run_zone_tripwire.py")
    assert path.exists()
    assert "Run Day-4 zone Tripwire v2" in path.read_text(encoding="utf-8")


def write_video(path: Path, frames: list[np.ndarray], *, fps: int) -> None:
    import cv2  # type: ignore

    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()
    assert path.exists()
