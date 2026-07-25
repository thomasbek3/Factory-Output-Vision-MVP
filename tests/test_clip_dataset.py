from __future__ import annotations

from pathlib import Path

import numpy as np

from app.services.clip_dataset import extract_clip_dataset
from app.services.training_exam_guard import sha256_file


def test_clip_extractor_writes_stack3_clip_flow_shapes_and_is_resumable(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    write_video(video, synthetic_frames(), fps=8)
    candidates = [
        {
            "candidate_id": "candidate-1",
            "source": str(video),
            "center_sec": 1.0,
            "start_sec": 0.0,
            "end_sec": 2.0,
            "source_start_at": "2026-07-25T12:00:00Z",
            "source_sha256": sha256_file(video),
            "lineage_source_sha256": [sha256_file(video)],
            "lineage_is_transitive_complete": True,
        }
    ]
    out_dir = tmp_path / "dataset"
    polygon = [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]

    first = extract_clip_dataset(
        candidates=candidates,
        output_dir=out_dir,
        output_zone_polygon=polygon,
        encoding="all",
        clip_fps=4,
        clip_frame_count=16,
    )
    paths = first["samples"][0]["paths"]
    mtimes = {name: Path(path).stat().st_mtime_ns for name, path in paths.items()}
    second = extract_clip_dataset(
        candidates=candidates,
        output_dir=out_dir,
        output_zone_polygon=polygon,
        encoding="all",
        clip_fps=4,
        clip_frame_count=16,
    )

    assert second["samples"][0]["paths"] == paths
    assert {name: Path(path).stat().st_mtime_ns for name, path in paths.items()} == mtimes
    assert np.load(paths["stack3"])["data"].shape == (3, 48, 24, 3)
    assert np.load(paths["clip"])["data"].shape == (16, 48, 24, 3)
    assert np.load(paths["flow"])["data"].shape == (15, 48, 24, 2)
    assert first["samples"][0]["label"] is None
    assert first["samples"][0]["source_sha256"] == sha256_file(video)
    assert first["samples"][0]["start_at"] == "2026-07-25T12:00:00Z"
    assert first["samples"][0]["end_at"] == "2026-07-25T12:00:02Z"


def synthetic_frames() -> list[np.ndarray]:
    frames = []
    for index in range(20):
        frame = np.zeros((48, 48, 3), dtype=np.uint8)
        frame[:, 24:48] = index * 10
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
