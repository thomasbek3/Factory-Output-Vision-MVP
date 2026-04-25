from pathlib import Path

import pytest

from scripts import select_video_frames as selector


def test_parse_args_uses_requested_defaults():
    args = selector.parse_args(["line.mp4"])

    assert args.videos == [Path("line.mp4")]
    assert args.out_dir == Path("data/videos/selected_frames")
    assert args.frames_per_video == 80
    assert args.min_interval_seconds == 2.0
    assert args.scene_threshold == 0.18
    assert args.force is False


def test_uniform_timestamps_spread_across_duration_and_cap_count():
    assert selector.uniform_timestamps(duration=10.0, frames_per_video=5) == [
        1.0,
        3.0,
        5.0,
        7.0,
        9.0,
    ]


def test_uniform_timestamps_reject_invalid_values():
    with pytest.raises(ValueError, match="duration"):
        selector.uniform_timestamps(duration=0, frames_per_video=5)
    with pytest.raises(ValueError, match="frames"):
        selector.uniform_timestamps(duration=10, frames_per_video=0)


def test_filter_min_interval_sorts_dedupes_and_preserves_reason():
    candidates = [
        selector.TimestampCandidate(timestamp=5.4, selection_reason="uniform"),
        selector.TimestampCandidate(timestamp=1.0, selection_reason="uniform"),
        selector.TimestampCandidate(timestamp=2.0, selection_reason="scene"),
        selector.TimestampCandidate(timestamp=3.2, selection_reason="uniform"),
        selector.TimestampCandidate(timestamp=5.4, selection_reason="scene"),
    ]

    selected = selector.filter_min_interval(candidates, min_interval_seconds=2.0, limit=3)

    assert selected == [
        selector.TimestampCandidate(timestamp=1.0, selection_reason="uniform"),
        selector.TimestampCandidate(timestamp=3.2, selection_reason="uniform"),
        selector.TimestampCandidate(timestamp=5.4, selection_reason="uniform"),
    ]


def test_filter_min_interval_rejects_invalid_values():
    with pytest.raises(ValueError, match="min interval"):
        selector.filter_min_interval([], min_interval_seconds=0, limit=1)
    with pytest.raises(ValueError, match="limit"):
        selector.filter_min_interval([], min_interval_seconds=1, limit=0)


def test_safe_frame_filename_sanitizes_stem_and_formats_timestamp():
    filename = selector.safe_frame_filename(Path("/tmp/Factory Line #1: shift A.mov"), 123.45)

    assert filename == "Factory_Line_1_shift_A_t000123.45.jpg"


def test_safe_frame_filename_uses_fallback_and_rejects_negative_timestamp():
    assert selector.safe_frame_filename(Path("////.mp4"), 0.0) == "video_t000000.00.jpg"
    with pytest.raises(ValueError, match="timestamp"):
        selector.safe_frame_filename(Path("input.mp4"), -0.01)


def test_build_manifest_row_uses_repo_relative_paths_and_metadata(tmp_path):
    repo_root = tmp_path
    video_path = repo_root / "data" / "videos" / "line 1.mp4"
    frame_path = repo_root / "data" / "videos" / "selected_frames" / "line_1_t000001.00.jpg"
    metadata = selector.VideoMetadata(duration=12.5, width=1920, height=1080)

    row = selector.build_manifest_row(
        video_path=video_path,
        frame_path=frame_path,
        timestamp=1.0,
        selection_reason="uniform",
        metadata=metadata,
        repo_root=repo_root,
    )

    assert row == {
        "video_path": "data/videos/line 1.mp4",
        "frame_path": "data/videos/selected_frames/line_1_t000001.00.jpg",
        "timestamp_seconds": 1.0,
        "selection_reason": "uniform",
        "width": 1920,
        "height": 1080,
        "duration": 12.5,
    }


def test_build_extract_frame_command_uses_absolute_paths_and_no_shell():
    command = selector.build_extract_frame_command(
        video_path=Path("-input.mp4"),
        frame_path=Path("-frame.jpg"),
        timestamp=12.345,
        force=False,
    )

    video_arg = command[command.index("-i") + 1]
    output_arg = command[-1]
    assert command == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-ss",
        "12.345",
        "-i",
        str(Path("-input.mp4").resolve()),
        "-frames:v",
        "1",
        str(Path("-frame.jpg").resolve()),
    ]
    assert Path(video_arg).is_absolute()
    assert Path(output_arg).is_absolute()
    assert not video_arg.startswith("-")
    assert not output_arg.startswith("-")


def test_build_extract_frame_command_uses_force_overwrite_flag():
    command = selector.build_extract_frame_command(
        video_path=Path("input.mp4"),
        frame_path=Path("frame.jpg"),
        timestamp=1.0,
        force=True,
    )

    assert "-y" in command
    assert "-n" not in command


def test_select_frames_refuses_existing_manifest_without_force(tmp_path):
    out_dir = tmp_path / "selected"
    out_dir.mkdir()
    (out_dir / selector.MANIFEST_NAME).write_text("[]\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="manifest"):
        selector.select_frames(
            video_paths=[tmp_path / "line.mp4"],
            out_dir=out_dir,
            frames_per_video=1,
            min_interval_seconds=1.0,
            scene_threshold=0.18,
            force=False,
            repo_root=tmp_path,
        )


def test_select_frames_refuses_existing_frame_without_force(tmp_path, monkeypatch):
    video_path = tmp_path / "line.mp4"
    video_path.write_text("not a real video", encoding="utf-8")
    out_dir = tmp_path / "selected"
    out_dir.mkdir()
    existing_frame = out_dir / "line_t000005.00.jpg"
    existing_frame.write_text("old", encoding="utf-8")

    monkeypatch.setattr(
        selector,
        "ffprobe_metadata",
        lambda path: selector.VideoMetadata(duration=10.0, width=640, height=480),
    )

    with pytest.raises(FileExistsError, match="line_t000005.00.jpg"):
        selector.select_frames(
            video_paths=[video_path],
            out_dir=out_dir,
            frames_per_video=1,
            min_interval_seconds=1.0,
            scene_threshold=0.18,
            force=False,
            repo_root=tmp_path,
        )


def test_select_frames_extracts_and_writes_manifest_with_monkeypatched_helpers(tmp_path, monkeypatch):
    video_path = tmp_path / "line.mp4"
    video_path.write_text("not a real video", encoding="utf-8")
    out_dir = tmp_path / "selected"
    calls = []

    monkeypatch.setattr(
        selector,
        "ffprobe_metadata",
        lambda path: selector.VideoMetadata(duration=10.0, width=640, height=480),
    )

    def fake_extract(*, video_path, frame_path, timestamp, force):
        calls.append((video_path, frame_path, timestamp, force))
        frame_path.write_text("jpg", encoding="utf-8")

    monkeypatch.setattr(selector, "extract_frame", fake_extract)

    rows = selector.select_frames(
        video_paths=[video_path],
        out_dir=out_dir,
        frames_per_video=2,
        min_interval_seconds=2.0,
        scene_threshold=0.18,
        force=False,
        repo_root=tmp_path,
    )

    assert [row["timestamp_seconds"] for row in rows] == [2.5, 7.5]
    assert [row["selection_reason"] for row in rows] == ["uniform", "uniform"]
    assert len(calls) == 2
    assert (out_dir / selector.MANIFEST_NAME).exists()
    assert rows[0]["frame_path"] == "selected/line_t000002.50.jpg"
