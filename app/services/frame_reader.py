import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.core.settings import get_reader_fps
from app.services.video_source import SourceSelection

logger = logging.getLogger(__name__)


@dataclass
class ReaderSnapshot:
    frame: Optional[np.ndarray]
    last_frame_time: float
    source: Optional[str]


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

    def start(self, selection: SourceSelection, width: int, height: int, demo_playback_speed: float = 1.0) -> None:
        with self._lock:
            if (
                self._source == selection.source
                and self._thread
                and self._thread.is_alive()
                and (not selection.is_demo or abs(self._demo_playback_speed - demo_playback_speed) < 1e-6)
            ):
                return
        self.stop()
        self._source = selection.source
        self._width = max(int(width), 1)
        self._height = max(int(height), 1)
        self._demo_playback_speed = max(0.25, min(float(demo_playback_speed), 8.0))
        self._stop_event.clear()
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
        self._thread = None
        self._process = None

    def restart(self) -> None:
        self.stop()

    def snapshot(self) -> ReaderSnapshot:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            return ReaderSnapshot(frame=frame, last_frame_time=self._last_frame_time, source=self._source)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "source": self._source,
                "thread_alive": bool(self._thread and self._thread.is_alive()),
                "process_alive": bool(self._process and self._process.poll() is None),
                "last_frame_time": self._last_frame_time,
                "last_error": self._last_error,
                "demo_playback_speed": self._demo_playback_speed,
            }

    def _build_cmd(self, selection: SourceSelection) -> list[str]:
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        if selection.is_demo:
            base += ["-stream_loop", "-1", "-readrate", f"{self._demo_playback_speed:g}", "-i", selection.source]
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
                        self._set_last_error("ffmpeg stream returned incomplete frame")
                        break
                    arr = np.frombuffer(raw, dtype=np.uint8).reshape((self._height, self._width, 3))
                    with self._lock:
                        self._frame = arr
                        self._last_frame_time = time.time()
                        self._last_error = None
                if self._stop_event.is_set():
                    break
            finally:
                stderr_text = self._cleanup_process(process)
                if stderr_text:
                    self._set_last_error(stderr_text[:500])
                    logger.warning("ffmpeg reader stderr: %s", stderr_text[:500])
                if self._process is process:
                    self._process = None
            time.sleep(0.5)

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
