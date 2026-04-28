from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.settings import get_demo_playback_speed, is_demo_mode
from app.services.demo_video_library import get_active_demo_video, set_active_demo_video
from app.services.camera_probe import ffprobe_stream
from app.services.frame_reader import FFmpegFrameReader
from app.services.video_source import SourceSelection, get_active_source

logger = logging.getLogger(__name__)


@dataclass
class RuntimeStatus:
    source: SourceSelection
    width: int
    height: int


class VideoRuntime:
    def __init__(self) -> None:
        self.reader = FFmpegFrameReader()
        self._active_source: str | None = None
        self._demo_playback_speed = max(0.25, min(get_demo_playback_speed(), 8.0))
        self._demo_source_override = str(get_active_demo_video()) if get_active_demo_video() is not None else None

    def current_source_selection(self) -> SourceSelection:
        selection = get_active_source()
        if selection.is_demo and self._demo_source_override:
            return SourceSelection(is_demo=True, source=self._demo_source_override, candidates=(self._demo_source_override,))
        return selection

    def _resolve_source(self, selection: SourceSelection) -> tuple[str, dict[str, Any]]:
        if selection.is_demo:
            details = ffprobe_stream(selection.source)
            return selection.source, details

        last_error: Exception | None = None
        for candidate in selection.candidates:
            try:
                details = ffprobe_stream(candidate)
                return candidate, details
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        raise RuntimeError(f"Unable to open RTSP stream candidates: {last_error}")

    def ensure_running(self) -> RuntimeStatus:
        selection = self.current_source_selection()
        if self._active_source not in selection.candidates:
            resolved_source, metadata = self._resolve_source(selection)
            width = int(metadata.get("width") or 640)
            height = int(metadata.get("height") or 360)
            resolved = SourceSelection(
                is_demo=selection.is_demo,
                source=resolved_source,
                candidates=(resolved_source,),
            )
            self.reader.start(
                resolved,
                width=width,
                height=height,
                demo_playback_speed=self._demo_playback_speed if resolved.is_demo else 1.0,
            )
            self._active_source = resolved_source
            return RuntimeStatus(source=resolved, width=width, height=height)

        snap = self.reader.snapshot()
        width = snap.frame.shape[1] if snap.frame is not None else 640
        height = snap.frame.shape[0] if snap.frame is not None else 360
        return RuntimeStatus(source=selection, width=width, height=height)

    def restart(self) -> RuntimeStatus:
        logger.info("Restarting video runtime")
        self.reader.stop()
        self._active_source = None
        return self.ensure_running()

    def current_source_kind(self) -> str:
        try:
            selection = self.current_source_selection()
            return "demo" if selection.is_demo else "camera"
        except Exception:  # noqa: BLE001
            return "demo" if is_demo_mode() else "camera"

    def current_demo_playback_speed(self) -> float:
        return self._demo_playback_speed

    def set_demo_playback_speed(self, speed: float) -> RuntimeStatus:
        if self.current_source_kind() != "demo":
            raise RuntimeError("Demo playback speed can only be changed in demo mode")
        self._demo_playback_speed = max(0.25, min(float(speed), 8.0))
        return self.restart()

    def set_demo_video_source(self, path: str) -> RuntimeStatus:
        if self.current_source_kind() != "demo":
            raise RuntimeError("Demo video can only be changed in demo mode")
        selected = set_active_demo_video(path)
        self._demo_source_override = str(selected)
        return self.restart()

    def current_demo_video_name(self) -> str | None:
        if self.current_source_kind() != "demo":
            return None
        source = self._demo_source_override or str(get_active_demo_video() or "")
        return None if not source else Path(source).name
