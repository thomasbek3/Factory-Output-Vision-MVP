from __future__ import annotations

from app.services.frame_reader import FFmpegFrameReader
from app.services.video_source import SourceSelection


def test_demo_reader_omits_stream_loop_when_single_pass_disabled() -> None:
    reader = FFmpegFrameReader()
    reader._width = 640
    reader._height = 360
    reader._demo_playback_speed = 8.0
    reader._demo_loop_enabled = False

    command = reader._build_cmd(SourceSelection(is_demo=True, source="/tmp/demo.mov", candidates=("/tmp/demo.mov",)))

    assert "-stream_loop" not in command
    assert "-readrate" in command
    assert "/tmp/demo.mov" in command


def test_demo_reader_keeps_stream_loop_when_looping_enabled() -> None:
    reader = FFmpegFrameReader()
    reader._width = 640
    reader._height = 360
    reader._demo_playback_speed = 2.0
    reader._demo_loop_enabled = True

    command = reader._build_cmd(SourceSelection(is_demo=True, source="/tmp/demo.mov", candidates=("/tmp/demo.mov",)))

    assert "-stream_loop" in command
    assert "-1" in command
