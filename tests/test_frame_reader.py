from __future__ import annotations

import numpy as np

from app.services.frame_reader import FFmpegFrameReader, ReaderSnapshot
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


def test_consume_next_frame_returns_frames_in_fifo_order() -> None:
    reader = FFmpegFrameReader()
    first = np.zeros((2, 2, 3), dtype=np.uint8)
    second = np.ones((2, 2, 3), dtype=np.uint8)

    reader._source = "demo"
    reader._pending_frames.append(ReaderSnapshot(frame=first, last_frame_time=1.0, source="demo"))
    reader._pending_frames.append(ReaderSnapshot(frame=second, last_frame_time=2.0, source="demo"))

    first_out = reader.consume_next_frame()
    second_out = reader.consume_next_frame()

    assert first_out is not None
    assert second_out is not None
    assert int(first_out.frame[0, 0, 0]) == 0
    assert int(second_out.frame[0, 0, 0]) == 1
    assert reader.consume_next_frame() is None


def test_discard_pending_frames_clears_queue() -> None:
    reader = FFmpegFrameReader()
    reader._pending_frames.append(ReaderSnapshot(frame=np.zeros((1, 1, 3), dtype=np.uint8), last_frame_time=1.0, source="demo"))

    reader.discard_pending_frames()

    assert reader.consume_next_frame() is None
