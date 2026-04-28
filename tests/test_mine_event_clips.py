from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import mine_event_clips as miner


def test_score_motion_windows_prefers_zone_motion_and_applies_min_gap() -> None:
    samples = [
        miner.MotionSample(timestamp=0.0, source_motion=0.0, output_motion=0.0, transfer_motion=0.0, global_motion=0.0),
        miner.MotionSample(timestamp=5.0, source_motion=0.8, output_motion=0.7, transfer_motion=0.9, global_motion=0.2),
        miner.MotionSample(timestamp=10.0, source_motion=0.7, output_motion=0.6, transfer_motion=0.8, global_motion=0.2),
        miner.MotionSample(timestamp=30.0, source_motion=0.1, output_motion=0.9, transfer_motion=0.9, global_motion=0.1),
    ]

    windows = miner.score_motion_windows(
        samples,
        clip_seconds=12.0,
        pre_roll_seconds=3.0,
        limit=2,
        min_gap_seconds=15.0,
    )

    assert [window.center_timestamp for window in windows] == [5.0, 30.0]
    assert windows[0].start_timestamp == 2.0
    assert windows[0].end_timestamp == 14.0
    assert windows[0].score > windows[1].score
    assert windows[0].selection_reason == "source_output_transfer_motion"


def test_write_event_manifest_refuses_overwrite_without_force(tmp_path: Path) -> None:
    out_dir = tmp_path / "events"
    out_dir.mkdir()
    (out_dir / "manifest.json").write_text("[]", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--force"):
        miner.prepare_output_dir(out_dir, force=False)


def test_mine_event_clips_writes_manifest_and_sheet_rows_with_fake_backend(tmp_path: Path) -> None:
    video = tmp_path / "factory2.MOV"
    video.write_text("not a real video", encoding="utf-8")
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "source_polygons": [[[60, 0], [100, 0], [100, 100], [60, 100]]],
                "output_polygons": [[[0, 0], [40, 0], [40, 100], [0, 100]]],
                "ignore_polygons": [],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    def fake_metadata(path: Path) -> miner.VideoMetadata:
        return miner.VideoMetadata(duration=60.0, width=100, height=100)

    def fake_samples(**kwargs):
        return [
            miner.MotionSample(timestamp=5.0, source_motion=0.8, output_motion=0.7, transfer_motion=0.9, global_motion=0.2),
            miner.MotionSample(timestamp=25.0, source_motion=0.1, output_motion=0.9, transfer_motion=0.8, global_motion=0.2),
        ]

    extracted = []
    sheets = []

    def fake_extract_clip(**kwargs):
        extracted.append(kwargs)
        kwargs["output_path"].write_text("clip", encoding="utf-8")

    def fake_make_sheet(**kwargs):
        sheets.append(kwargs)
        kwargs["output_path"].write_text("sheet", encoding="utf-8")

    result = miner.mine_event_clips(
        video_path=video,
        calibration_path=calibration,
        out_dir=out_dir,
        limit=2,
        clip_seconds=10.0,
        pre_roll_seconds=2.0,
        sample_fps=1.0,
        min_gap_seconds=10.0,
        force=False,
        metadata_loader=fake_metadata,
        motion_sampler=fake_samples,
        clip_extractor=fake_extract_clip,
        sheet_maker=fake_make_sheet,
        repo_root=tmp_path,
    )

    assert len(result["events"]) == 2
    assert result["events"][0]["clip_path"].endswith("factory2_event_0001_t000005.00.mp4")
    assert result["events"][0]["sheet_path"].endswith("factory2_event_0001_t000005.00.jpg")
    assert len(extracted) == 2
    assert len(sheets) == 2
    assert json.loads((out_dir / "manifest.json").read_text(encoding="utf-8")) == result
