from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.core.settings import get_processing_fps, get_reader_fps
from app.services.video_source import SourceSelection

logger = logging.getLogger(__name__)


@dataclass
class ReaderSnapshot:
    frame: Optional[np.ndarray]
    last_frame_time: float
    source: Optional[str]
    sequence_index: int = 0
    source_timestamp_sec: float | None = None


class FFmpegFrameReader:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._last_frame_time = 0.0
        self._source: Optional[str] = None
        self._last_error: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._width = 0
        self._height = 0
        self._demo_playback_speed = 1.0
        self._demo_finished = False
        self._demo_loop_enabled = True
        self._pending_frames: deque[ReaderSnapshot] = deque()
        self._max_pending_frames = 240
        self._dropped_frame_count = 0
        self._sequence_index = 0
        self._last_source_timestamp_sec: float | None = None
        self._sync_demo_capture: Optional[cv2.VideoCapture] = None
        self._sync_demo_frame_indices: list[int] = []
        self._sync_demo_cursor = 0
        self._sync_demo_video_fps = 0.0
        self._sync_demo_last_frame_index = -1
        self._sync_demo_buffered_frame: Optional[np.ndarray] = None
        self._sync_demo_buffered_frame_index = -1
        self._sync_demo_started_at_ts: float | None = None

    def start(
        self,
        selection: SourceSelection,
        width: int,
        height: int,
        demo_playback_speed: float = 1.0,
        demo_loop_enabled: bool = True,
    ) -> None:
        with self._lock:
            if (
                self._source == selection.source
                and self._thread
                and self._thread.is_alive()
                and (
                    not selection.is_demo
                    or (
                        abs(self._demo_playback_speed - demo_playback_speed) < 1e-6
                        and self._demo_loop_enabled == bool(demo_loop_enabled)
                    )
                )
            ):
                return
        self.stop()
        self._source = selection.source
        self._width = max(int(width), 1)
        self._height = max(int(height), 1)
        self._demo_playback_speed = max(0.25, min(float(demo_playback_speed), 8.0))
        self._demo_loop_enabled = bool(demo_loop_enabled)
        self._demo_finished = False
        with self._lock:
            self._pending_frames.clear()
            self._dropped_frame_count = 0
            self._sequence_index = 0
            self._last_source_timestamp_sec = None
            self._frame = None
            self._last_frame_time = 0.0
            self._last_error = None
        self._stop_event.clear()
        if selection.is_demo and not self._demo_loop_enabled:
            self._start_synchronous_demo(selection)
            return
        self._thread = threading.Thread(
            target=self._read_loop,
            args=(selection,),
            name="ffmpeg-frame-reader",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        process = self._process
        if process and process.poll() is None:
            self._terminate_process(process, close_pipes=False)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if process:
            self._cleanup_process(process, include_stderr=False)
        with self._lock:
            sync_demo_capture = self._sync_demo_capture
            self._sync_demo_capture = None
            self._sync_demo_frame_indices = []
            self._sync_demo_cursor = 0
            self._sync_demo_video_fps = 0.0
            self._sync_demo_last_frame_index = -1
            self._sync_demo_buffered_frame = None
            self._sync_demo_buffered_frame_index = -1
            self._sync_demo_started_at_ts = None
        self._thread = None
        self._process = None
        if sync_demo_capture is not None:
            sync_demo_capture.release()
        with self._lock:
            self._frame = None
            self._last_frame_time = 0.0
            self._last_source_timestamp_sec = None
            self._pending_frames.clear()

    def restart(self) -> None:
        self.stop()

    def snapshot(self) -> ReaderSnapshot:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            return ReaderSnapshot(
                frame=frame,
                last_frame_time=self._last_frame_time,
                source=self._source,
                sequence_index=self._sequence_index,
                source_timestamp_sec=self._last_source_timestamp_sec,
            )

    def consume_next_frame(self) -> Optional[ReaderSnapshot]:
        with self._lock:
            if not self._pending_frames:
                return None
            return self._pending_frames.popleft()

    def pump_next_demo_frame(self) -> Optional[ReaderSnapshot]:
        with self._lock:
            capture = self._sync_demo_capture
            if capture is None:
                return None
            if self._sync_demo_cursor >= len(self._sync_demo_frame_indices):
                self._demo_finished = True
                return None
            frame_index = self._sync_demo_frame_indices[self._sync_demo_cursor]
            source_timestamp_sec = frame_index / max(self._sync_demo_video_fps, 1.0)
            if self._sync_demo_started_at_ts is None:
                self._sync_demo_started_at_ts = time.time()
            self._sleep_until(
                self._sync_demo_started_at_ts
                + (source_timestamp_sec / max(self._demo_playback_speed, 0.01))
            )
            if (
                self._sync_demo_buffered_frame is not None
                and frame_index == self._sync_demo_buffered_frame_index
            ):
                frame = self._sync_demo_buffered_frame
                self._sync_demo_buffered_frame = None
                self._sync_demo_buffered_frame_index = -1
            else:
                frame = self._read_demo_frame(capture, frame_index)
            if frame is None:
                self._demo_finished = True
                return None
            frame_time = time.time()
            self._sync_demo_cursor += 1
            self._sequence_index += 1
            self._frame = frame
            self._last_frame_time = frame_time
            self._last_error = None
            self._last_source_timestamp_sec = source_timestamp_sec
            self._demo_finished = self._sync_demo_cursor >= len(self._sync_demo_frame_indices)
            return ReaderSnapshot(
                frame=None if self._frame is None else self._frame.copy(),
                last_frame_time=self._last_frame_time,
                source=self._source,
                sequence_index=self._sequence_index,
                source_timestamp_sec=self._last_source_timestamp_sec,
            )

    def is_synchronous_demo_mode(self) -> bool:
        with self._lock:
            return self._sync_demo_capture is not None

    def discard_pending_frames(self) -> None:
        with self._lock:
            self._pending_frames.clear()

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "source": self._source,
                "thread_alive": bool((self._thread and self._thread.is_alive()) or self._sync_demo_capture is not None),
                "process_alive": bool((self._process and self._process.poll() is None) or self._sync_demo_capture is not None),
                "last_frame_time": self._last_frame_time,
                "last_error": self._last_error,
                "demo_playback_speed": self._demo_playback_speed,
                "demo_finished": self._demo_finished,
                "demo_loop_enabled": self._demo_loop_enabled,
                "pending_frames": len(self._pending_frames),
                "dropped_frames": self._dropped_frame_count,
                "last_sequence_index": self._sequence_index,
                "last_source_timestamp_sec": self._last_source_timestamp_sec,
                "sync_demo_mode": self._sync_demo_capture is not None,
            }

    def _start_synchronous_demo(self, selection: SourceSelection) -> None:
        capture = cv2.VideoCapture(selection.source)
        if not capture.isOpened():
            self._set_last_error("Unable to open demo video")
            with self._lock:
                self._demo_finished = True
            return
        video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_indices = _sampled_frame_indices(
            video_fps=video_fps,
            frame_count=frame_count,
            output_fps=get_processing_fps(),
        )
        preview = None
        if frame_indices:
            preview = self._read_demo_frame(capture, frame_indices[0])
        with self._lock:
            self._sync_demo_capture = capture
            self._sync_demo_frame_indices = frame_indices
            self._sync_demo_cursor = 0
            self._sync_demo_video_fps = max(float(video_fps), 1.0)
            self._sync_demo_last_frame_index = frame_indices[0] if preview is not None and frame_indices else -1
            self._sync_demo_buffered_frame = preview
            self._sync_demo_buffered_frame_index = frame_indices[0] if preview is not None and frame_indices else -1
            self._sync_demo_started_at_ts = None
            self._demo_finished = len(frame_indices) == 0
            self._last_source_timestamp_sec = None
            if preview is not None:
                self._frame = preview
                self._last_frame_time = time.time()
                self._last_error = None

    def _read_demo_frame(self, capture: cv2.VideoCapture, frame_index: int) -> Optional[np.ndarray]:
        if self._sync_demo_last_frame_index < 0 or frame_index <= self._sync_demo_last_frame_index:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        else:
            frames_to_skip = frame_index - self._sync_demo_last_frame_index - 1
            for _ in range(max(frames_to_skip, 0)):
                if not capture.grab():
                    return None
        ok, frame = capture.read()
        if not ok:
            return None
        self._sync_demo_last_frame_index = frame_index
        if frame.shape[1] != self._width or frame.shape[0] != self._height:
            frame = cv2.resize(frame, (self._width, self._height), interpolation=cv2.INTER_LINEAR)
        return frame

    def _build_cmd(self, selection: SourceSelection) -> list[str]:
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        if selection.is_demo:
            if self._demo_loop_enabled:
                base += ["-stream_loop", "-1"]
            base += ["-readrate", f"{self._demo_playback_speed:g}", "-i", selection.source]
        else:
            base += ["-rtsp_transport", "tcp", "-i", selection.source]
        reader_fps = max(1.0, get_reader_fps())
        base += [
            "-vf",
            f"fps={reader_fps:g},scale={self._width}:{self._height}",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        return base

    def _read_loop(self, selection: SourceSelection) -> None:
        if selection.is_demo and not self._demo_loop_enabled:
            self._read_single_pass_demo_loop(selection)
            return

        frame_bytes = self._width * self._height * 3
        while not self._stop_event.is_set():
            cmd = self._build_cmd(selection)
            logger.info("Starting ffmpeg reader for source=%s", selection.source)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._process = process
            try:
                while not self._stop_event.is_set():
                    if not process.stdout:
                        self._set_last_error("ffmpeg stdout unavailable")
                        break
                    raw = process.stdout.read(frame_bytes)
                    if len(raw) != frame_bytes:
                        if self._is_demo_eof(selection, process, raw):
                            with self._lock:
                                self._demo_finished = True
                                self._last_error = None
                            break
                        self._set_last_error("ffmpeg stream returned incomplete frame")
                        break
                    arr = np.frombuffer(raw, dtype=np.uint8).reshape((self._height, self._width, 3))
                    frame_time = time.time()
                    with self._lock:
                        self._sequence_index += 1
                        self._frame = arr
                        self._last_frame_time = frame_time
                        self._last_error = None
                        self._last_source_timestamp_sec = None
                        self._pending_frames.append(
                            ReaderSnapshot(
                                frame=arr,
                                last_frame_time=frame_time,
                                source=self._source,
                                sequence_index=self._sequence_index,
                                source_timestamp_sec=None,
                            )
                        )
                        while len(self._pending_frames) > self._max_pending_frames:
                            self._pending_frames.popleft()
                            self._dropped_frame_count += 1
                if self._stop_event.is_set():
                    break
            finally:
                stderr_text = self._cleanup_process(process)
                if stderr_text and not self._demo_finished:
                    self._set_last_error(stderr_text[:500])
                    logger.warning("ffmpeg reader stderr: %s", stderr_text[:500])
                if self._process is process:
                    self._process = None
            if self._demo_finished:
                while not self._stop_event.is_set():
                    time.sleep(0.1)
                break
            time.sleep(0.5)

    def _read_single_pass_demo_loop(self, selection: SourceSelection) -> None:
        logger.info("Starting sampled demo reader for source=%s", selection.source)
        capture = cv2.VideoCapture(selection.source)
        if not capture.isOpened():
            self._set_last_error("Unable to open demo video")
            return

        try:
            video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frame_indices = _sampled_frame_indices(video_fps=video_fps, frame_count=frame_count, output_fps=get_reader_fps())
            started = time.time()

            for frame_index in frame_indices:
                if self._stop_event.is_set():
                    break
                self._wait_for_queue_capacity(max_pending_frames=1)
                if self._stop_event.is_set():
                    break
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = capture.read()
                if not ok:
                    break
                if frame.shape[1] != self._width or frame.shape[0] != self._height:
                    frame = cv2.resize(frame, (self._width, self._height), interpolation=cv2.INTER_LINEAR)

                target_offset = (frame_index / max(video_fps, 1.0)) / max(self._demo_playback_speed, 0.01)
                self._sleep_until(started + target_offset)
                if self._stop_event.is_set():
                    break

                frame_time = time.time()
                with self._lock:
                    self._sequence_index += 1
                    self._frame = frame
                    self._last_frame_time = frame_time
                    self._last_error = None
                    self._last_source_timestamp_sec = frame_index / max(video_fps, 1.0)
                    self._pending_frames.append(
                        ReaderSnapshot(
                            frame=frame,
                            last_frame_time=frame_time,
                            source=self._source,
                            sequence_index=self._sequence_index,
                            source_timestamp_sec=self._last_source_timestamp_sec,
                        )
                    )
                    while len(self._pending_frames) > self._max_pending_frames:
                        self._pending_frames.popleft()
                        self._dropped_frame_count += 1

            with self._lock:
                self._demo_finished = True
                self._last_error = None
            while not self._stop_event.is_set():
                time.sleep(0.1)
        finally:
            capture.release()

    def _is_demo_eof(self, selection: SourceSelection, process: subprocess.Popen[bytes], raw: bytes) -> bool:
        if not selection.is_demo or self._demo_loop_enabled:
            return False
        if len(raw) <= 0:
            if process.poll() is None:
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    return False
        elif process.poll() is None:
            return False
        with self._lock:
            return self._frame is not None and self._last_frame_time > 0

    def _sleep_until(self, target_ts: float) -> None:
        while not self._stop_event.is_set():
            remaining = target_ts - time.time()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.05))

    def _wait_for_queue_capacity(self, *, max_pending_frames: int) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if len(self._pending_frames) <= max_pending_frames:
                    return
            time.sleep(0.01)

    def _set_last_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message

    def _terminate_process(self, process: subprocess.Popen[bytes], *, close_pipes: bool) -> None:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg process did not exit cleanly after kill")
        if close_pipes:
            self._close_process_pipes(process)

    def _cleanup_process(self, process: subprocess.Popen[bytes], *, include_stderr: bool = True) -> str:
        self._terminate_process(process, close_pipes=False)
        stderr_text = ""
        stderr_stream = process.stderr
        if include_stderr and stderr_stream:
            try:
                stderr_text = stderr_stream.read().decode("utf-8", errors="ignore").strip()
            except Exception:  # noqa: BLE001
                stderr_text = ""
        self._close_process_pipes(process)
        return stderr_text

    def _close_process_pipes(self, process: subprocess.Popen[bytes]) -> None:
        for stream in (process.stdout, process.stderr):
            if stream is None:
                continue
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                pass


def encode_jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Failed to encode JPEG")
    return buf.tobytes()


def _sampled_frame_indices(*, video_fps: float, frame_count: int, output_fps: float) -> list[int]:
    fps = max(float(video_fps), 1.0)
    total_frames = max(int(frame_count), 0)
    selected_fps = max(float(output_fps), 0.1)
    if total_frames <= 0:
        return []
    if selected_fps >= fps:
        return list(range(total_frames))

    indices: list[int] = []
    timestamp = 0.0
    frame_interval = 1.0 / selected_fps
    while True:
        frame_index = int(timestamp * fps + 0.5)
        if frame_index >= total_frames:
            break
        if not indices or frame_index > indices[-1]:
            indices.append(frame_index)
        timestamp += frame_interval
    return indices
