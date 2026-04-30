from __future__ import annotations

import cv2
import numpy as np
from unittest.mock import Mock
from unittest.mock import patch

from app.services.frame_reader import FFmpegFrameReader, ReaderSnapshot, _sampled_frame_indices
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


def test_sampled_frame_indices_match_audit_stride() -> None:
    indices = _sampled_frame_indices(video_fps=29.97, frame_count=12, output_fps=10.0)

    assert indices == [0, 3, 6, 9]


def test_single_pass_demo_reader_pumps_processing_fps_frames_synchronously() -> None:
    class FakeCapture:
        def __init__(self) -> None:
            self.current_index = 0
            self.set_calls: list[int] = []

        def isOpened(self) -> bool:  # noqa: N802
            return True

        def get(self, prop: int) -> float:  # noqa: ANN001
            if prop == cv2.CAP_PROP_FPS:
                return 30.0
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return 6.0
            return 0.0

        def set(self, prop: int, value: float) -> bool:  # noqa: ANN001
            if prop == cv2.CAP_PROP_POS_FRAMES:
                self.current_index = int(value)
                self.set_calls.append(int(value))
            return True

        def read(self) -> tuple[bool, np.ndarray]:
            frame = np.full((2, 2, 3), self.current_index, dtype=np.uint8)
            return True, frame

        def release(self) -> None:
            return None

    capture = FakeCapture()
    reader = FFmpegFrameReader()

    with patch("app.services.frame_reader.cv2.VideoCapture", return_value=capture), patch(
        "app.services.frame_reader.get_processing_fps",
        return_value=10.0,
    ):
        reader.start(
            SourceSelection(is_demo=True, source="/tmp/demo.mov", candidates=("/tmp/demo.mov",)),
            width=2,
            height=2,
            demo_playback_speed=1.0,
            demo_loop_enabled=False,
        )

    primed = reader.snapshot()
    assert primed.frame is not None
    assert int(primed.frame[0, 0, 0]) == 0
    assert reader.is_synchronous_demo_mode() is True

    first = reader.pump_next_demo_frame()
    second = reader.pump_next_demo_frame()
    exhausted = reader.pump_next_demo_frame()

    assert first is not None
    assert first.sequence_index == 1
    assert first.source_timestamp_sec == 0.0
    assert int(first.frame[0, 0, 0]) == 0
    assert second is not None
    assert second.sequence_index == 2
    assert second.source_timestamp_sec == 0.1
    assert int(second.frame[0, 0, 0]) == 3
    assert exhausted is None
    assert capture.set_calls == [0, 0, 3]
    status = reader.status()
    assert status["demo_finished"] is True
    assert status["last_source_timestamp_sec"] == 0.1


def test_demo_eof_detected_after_empty_read_before_process_poll_updates() -> None:
    reader = FFmpegFrameReader()
    reader._demo_loop_enabled = False
    reader._frame = np.zeros((2, 2, 3), dtype=np.uint8)
    reader._last_frame_time = 1.0
    process = Mock()
    process.poll.side_effect = [None, 0]
    process.wait.return_value = 0

    is_eof = reader._is_demo_eof(
        SourceSelection(is_demo=True, source="/tmp/demo.mov", candidates=("/tmp/demo.mov",)),
        process,
        b"",
    )

    assert is_eof is True
    process.wait.assert_called_once()


def test_demo_eof_detected_after_partial_terminal_read_when_process_exited() -> None:
    reader = FFmpegFrameReader()
    reader._demo_loop_enabled = False
    reader._frame = np.zeros((2, 2, 3), dtype=np.uint8)
    reader._last_frame_time = 1.0
    process = Mock()
    process.poll.return_value = 0

    is_eof = reader._is_demo_eof(
        SourceSelection(is_demo=True, source="/tmp/demo.mov", candidates=("/tmp/demo.mov",)),
        process,
        b"partial",
    )

    assert is_eof is True
