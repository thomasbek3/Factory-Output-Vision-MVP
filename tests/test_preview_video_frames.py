from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import preview_video_frames as preview


def test_safe_video_stem_removes_unsafe_characters_and_keeps_readable_text():
    assert preview.safe_video_stem(Path("/tmp/Factory Line #1: shift A.mov")) == (
        "Factory_Line_1_shift_A"
    )


def test_safe_video_stem_uses_fallback_for_blank_names():
    assert preview.safe_video_stem(Path("////.mp4")) == "video"


def test_parse_ffprobe_json_extracts_duration_and_dimensions():
    payload = {
        "format": {"duration": "12.345"},
        "streams": [
            {"codec_type": "audio", "width": 0, "height": 0},
            {"codec_type": "video", "width": 1920, "height": 1080},
        ],
    }

    metadata = preview.parse_ffprobe_json(payload)

    assert metadata == preview.VideoMetadata(duration=12.345, width=1920, height=1080)


def test_parse_ffprobe_json_tolerates_missing_or_invalid_fields():
    payload = {
        "format": {"duration": "N/A"},
        "streams": [{"codec_type": "video", "width": "bad"}],
    }

    metadata = preview.parse_ffprobe_json(payload)

    assert metadata == preview.VideoMetadata(duration=None, width=None, height=None)


@pytest.mark.parametrize(
    ("duration", "frames", "expected"),
    [
        (8.0, 4, 2.0),
        (7.5, 3, 2.5),
        (None, 16, 1.0),
        (0.0, 16, 1.0),
        (-2.0, 16, 1.0),
    ],
)
def test_calculate_sample_interval(duration, frames, expected):
    assert preview.calculate_sample_interval(duration, frames) == expected


def test_calculate_sample_interval_rejects_non_positive_frame_count():
    with pytest.raises(ValueError, match="frames"):
        preview.calculate_sample_interval(10.0, 0)


def test_build_ffmpeg_filter_uses_fps_scale_and_tile_geometry():
    filter_value = preview.build_ffmpeg_filter(interval=2.5, cols=4, rows=3)

    assert filter_value == "fps=1/2.5,scale=320:-1:force_original_aspect_ratio=decrease,tile=4x3"


def test_build_ffmpeg_filter_rejects_invalid_values():
    with pytest.raises(ValueError, match="interval"):
        preview.build_ffmpeg_filter(interval=0, cols=4, rows=4)
    with pytest.raises(ValueError, match="cols"):
        preview.build_ffmpeg_filter(interval=1, cols=0, rows=4)
    with pytest.raises(ValueError, match="rows"):
        preview.build_ffmpeg_filter(interval=1, cols=4, rows=0)


def test_build_ffmpeg_command_returns_argv_list_and_uses_no_overwrite_by_default():
    command = preview.build_ffmpeg_command(
        video_path=Path("input.mp4"),
        output_path=Path("sheet.jpg"),
        interval=2.5,
        cols=4,
        rows=3,
        force=False,
    )

    assert command == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(Path("input.mp4").resolve()),
        "-vf",
        "fps=1/2.5,scale=320:-1:force_original_aspect_ratio=decrease,tile=4x3",
        "-frames:v",
        "1",
        str(Path("sheet.jpg").resolve()),
    ]


def test_build_ffmpeg_command_uses_force_overwrite_flag():
    command = preview.build_ffmpeg_command(
        video_path=Path("input.mp4"),
        output_path=Path("sheet.jpg"),
        interval=1,
        cols=2,
        rows=2,
        force=True,
    )

    assert "-y" in command
    assert "-n" not in command


def test_build_ffmpeg_command_resolves_dash_leading_relative_paths_to_absolute():
    command = preview.build_ffmpeg_command(
        video_path=Path("-input.mp4"),
        output_path=Path("-sheet.jpg"),
        interval=1,
        cols=2,
        rows=2,
        force=False,
    )

    video_arg = command[command.index("-i") + 1]
    output_arg = command[-1]
    assert video_arg == str(Path("-input.mp4").resolve())
    assert output_arg == str(Path("-sheet.jpg").resolve())
    assert Path(video_arg).is_absolute()
    assert Path(output_arg).is_absolute()
    assert not video_arg.startswith("-")
    assert not output_arg.startswith("-")


def test_ffprobe_metadata_reports_invalid_json(monkeypatch):
    def fake_run(command, check, capture_output, text):
        return SimpleNamespace(stdout="{invalid")

    monkeypatch.setattr(preview.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="invalid ffprobe JSON"):
        preview.ffprobe_metadata(Path("input.mp4"))


def test_build_manifest_row_uses_repo_relative_paths_when_possible(tmp_path):
    repo_root = tmp_path
    video_path = repo_root / "data" / "videos" / "line 1.mp4"
    output_path = repo_root / "data" / "videos" / "preview_sheets" / "line_1.jpg"
    metadata = preview.VideoMetadata(duration=6.0, width=1280, height=720)

    row = preview.build_manifest_row(
        video_path=video_path,
        output_path=output_path,
        metadata=metadata,
        interval=1.5,
        frames=4,
        cols=2,
        rows=2,
        repo_root=repo_root,
    )

    assert row == {
        "video_path": "data/videos/line 1.mp4",
        "duration": 6.0,
        "sheet_path": "data/videos/preview_sheets/line_1.jpg",
        "sampled_interval": 1.5,
        "frames": 4,
        "cols": 2,
        "rows": 2,
        "width": 1280,
        "height": 720,
    }
