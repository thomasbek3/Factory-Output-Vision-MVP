from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.auto_station_calibration import derive_station_calibration
from app.services.runtime_event_counter import load_runtime_calibration

WIDTH, HEIGHT = 640, 480


def _auto_boxes(tmp_path: Path) -> Path:
    path = tmp_path / "auto_boxes.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "auto-box-label-manifest-v1",
                "station_id": "line-a",
                "labels": [
                    {"box": [400.0, 300.0, 500.0, 360.0], "image_width": WIDTH, "image_height": HEIGHT},
                    {"box": [420.0, 320.0, 540.0, 400.0], "image_width": WIDTH, "image_height": HEIGHT},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _motion_provider():
    """Synthetic clip: a blob flickers in the TOP-LEFT corner (the 'machine'), far from the
    landing union in the bottom-right quadrant."""

    def _read(video_path: Path, timestamp_sec: float) -> np.ndarray:
        frame = np.full((HEIGHT, WIDTH, 3), 30, dtype=np.uint8)
        if int(timestamp_sec // 2) % 2 == 0:  # alternates between consecutive 0.5fps samples
            frame[40:160, 40:200] = (200, 200, 200)
        return frame

    return _read


def test_derives_zones_and_loader_accepts_artifact(tmp_path: Path, monkeypatch) -> None:
    import app.services.auto_station_calibration as module

    monkeypatch.setattr(module, "_video_duration_sec", lambda path: 30.0)
    auto_boxes = _auto_boxes(tmp_path)
    output = tmp_path / "station_calibration.json"

    payload = derive_station_calibration(
        auto_boxes_path=auto_boxes,
        train_clip_path=tmp_path / "train.MOV",
        output_path=output,
        frame_provider=_motion_provider(),
    )

    output_poly = payload["output_polygons"][0]
    xs = [point[0] for point in output_poly]
    ys = [point[1] for point in output_poly]
    # union (400,300)-(540,400) expanded by 10% of frame size (64, 48)
    assert min(xs) == pytest.approx(400 - 64, abs=1)
    assert max(xs) == pytest.approx(540 + 64, abs=1)
    assert min(ys) == pytest.approx(300 - 48, abs=1)
    assert max(ys) == pytest.approx(400 + 48, abs=1)

    source_poly = payload["source_polygons"][0]
    source_xs = [point[0] for point in source_poly]
    source_ys = [point[1] for point in source_poly]
    # the busiest region is the flickering top-left blob
    assert max(source_xs) < 300
    assert max(source_ys) < 250

    zones, gate = load_runtime_calibration(output)
    assert gate is None
    assert len(zones.output_polygons) == 1
    assert len(zones.source_polygons) == 1


def test_no_motion_falls_back_to_largest_strip(tmp_path: Path, monkeypatch) -> None:
    import app.services.auto_station_calibration as module

    monkeypatch.setattr(module, "_video_duration_sec", lambda path: 10.0)

    def _static(video_path: Path, timestamp_sec: float) -> np.ndarray:
        return np.full((HEIGHT, WIDTH, 3), 30, dtype=np.uint8)

    payload = derive_station_calibration(
        auto_boxes_path=_auto_boxes(tmp_path),
        train_clip_path=tmp_path / "train.MOV",
        output_path=tmp_path / "calibration.json",
        frame_provider=_static,
    )
    source_poly = payload["source_polygons"][0]
    assert source_poly  # non-empty fallback region
    zones, _ = load_runtime_calibration(tmp_path / "calibration.json")
    assert zones.source_polygons


def test_refuses_without_labels_and_respects_force(tmp_path: Path, monkeypatch) -> None:
    import app.services.auto_station_calibration as module

    monkeypatch.setattr(module, "_video_duration_sec", lambda path: 10.0)
    empty = tmp_path / "empty_boxes.json"
    empty.write_text(json.dumps({"labels": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no labels"):
        derive_station_calibration(
            auto_boxes_path=empty,
            train_clip_path=tmp_path / "train.MOV",
            output_path=tmp_path / "out.json",
            frame_provider=_motion_provider(),
        )

    output = tmp_path / "calibration.json"
    derive_station_calibration(
        auto_boxes_path=_auto_boxes(tmp_path),
        train_clip_path=tmp_path / "train.MOV",
        output_path=output,
        frame_provider=_motion_provider(),
    )
    with pytest.raises(FileExistsError):
        derive_station_calibration(
            auto_boxes_path=_auto_boxes(tmp_path),
            train_clip_path=tmp_path / "train.MOV",
            output_path=output,
            frame_provider=_motion_provider(),
        )
