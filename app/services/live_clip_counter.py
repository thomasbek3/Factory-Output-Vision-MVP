"""Live Track B counting: per-frame zone trigger -> buffered clip candidates ->
student judge -> debounced placement counts (ADR-0004).

Deep seam between the frame-paced VisionWorker loop and the exam kernel's
counting machinery (app.services.placement_counter). The runtime feeds frames
and timestamps into one interface and receives count events plus debug payload.

Contract notes (mirrors the blind-exam candidate stream):
- A clip window opens on the first zone trigger and extends while the zone
  stays busy. When the zone has been calm for cooldown_after_trigger_sec the
  window closes: the student judges the buffered clip, and the calm timestamp
  is fed to the counter as a QUIET observation — the same quiet-closes-
  placement rule the exam kernel relies on (PlacementCounter emits a count
  only on quiet, never on the assert itself).
- Frames are retained in a bounded rolling buffer so a judged descriptor can
  carry actual pixels (frames_small_bgr, stride-sampled). Until a tensor
  renderer for the promoted student exists, VisionWorker wires a stub judge
  that refutes with an explicit reason; swap the factory, not this module.
- The trigger is ROI-masked (normalized polygon, default whole frame) and
  deliberately high-recall: false alarms cost one judge call, misses are
  forever. min_candidate_gap_sec is a refractory period after a clip closes
  so residual motion cannot instantly reopen a new window.
- Nothing here mutates the runtime total: VisionWorker stays the system of
  record and records emitted events under its lock (ADR-0001/0005).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.settings import get_counting_mode
from app.services.placement_counter import PlacementCounter, PlacementVerdict

logger = logging.getLogger(__name__)

STUDENT_JUDGE_FACTORY = Callable[[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]

_SMALL_W, _SMALL_H = 256, 144


class LiveClipCounterConfigError(ValueError):
    """Raised when live Track B configuration is invalid at activation."""


@dataclass(frozen=True)
class LiveClipCounterSettings:
    model_path: str
    bracket_sec: float = 8.0
    sample_stride: int = 3
    pixel_change_threshold: float = 0.02
    min_candidate_gap_sec: float = 1.0
    cooldown_after_trigger_sec: float = 16.0
    debounce_sec: float = 25.0
    roi_polygon: tuple[tuple[float, float], ...] = (
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    )


def load_settings_from_env() -> LiveClipCounterSettings:
    """Read live Track B settings from FC_CLIP_* environment variables."""
    import json
    import os

    def _float(name: str, default: float) -> float:
        raw = os.getenv(name)
        return default if not raw else float(raw)

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        return default if not raw else int(raw)

    roi_polygon: tuple[tuple[float, float], ...] = LiveClipCounterSettings.__dataclass_fields__[
        "roi_polygon"
    ].default
    raw_roi = os.getenv("FC_CLIP_ROI_POLYGON")
    if raw_roi:
        try:
            points = json.loads(raw_roi)
            roi_polygon = tuple((float(p[0]), float(p[1])) for p in points)
        except (ValueError, TypeError) as exc:
            raise LiveClipCounterConfigError(f"FC_CLIP_ROI_POLYGON is invalid: {exc}") from exc

    return LiveClipCounterSettings(
        model_path=os.getenv("FC_CLIP_STUDENT_MODEL_PATH", ""),
        bracket_sec=_float("FC_CLIP_BRACKET_SEC", 8.0),
        sample_stride=_int("FC_CLIP_SAMPLE_STRIDE", 3),
        pixel_change_threshold=_float("FC_CLIP_PIXEL_CHANGE_THRESHOLD", 0.02),
        min_candidate_gap_sec=_float("FC_CLIP_MIN_CANDIDATE_GAP_SEC", 1.0),
        cooldown_after_trigger_sec=_float("FC_CLIP_COOLDOWN_SEC", 16.0),
        debounce_sec=_float("FC_CLIP_DEBOUNCE_SEC", 25.0),
        roi_polygon=roi_polygon,
    )


def _stub_judge_requiring_renderer(config: dict[str, Any]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Default production judge: refutes with an explicit missing-renderer reason.

    Promoted bundles consume extracted clip tensors (app.services.clip_models);
    rendering buffered live pixels into those tensors is not implemented yet,
    so the honest default is refute-with-reason rather than pretending.
    """

    def judge(descriptor: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": "refute",
            "score": 0.0,
            "reason": "pixel rendering for live clips is not implemented; "
            "wire a judge factory over frames_small_bgr to enable live scoring",
            "model_path": str(config.get("model_path", "")),
        }

    return judge


@dataclass
class _PendingClip:
    first_trigger_sec: float
    last_trigger_sec: float

    @property
    def start_sec(self) -> float:
        return max(0.0, self.first_trigger_sec)

    def end_sec(self, *, quiet_sec: float, bracket_sec: float) -> float:
        """Trained layout is center +/- bracket; cap the after-bracket at the
        moment calm was actually observed."""
        return min(self.last_trigger_sec + bracket_sec, quiet_sec)


class LiveClipCounter:
    """Per-frame Track B counter owned by VisionWorker when enabled."""

    def __init__(
        self,
        *,
        settings: LiveClipCounterSettings,
        judge_factory: STUDENT_JUDGE_FACTORY,
    ) -> None:
        if settings.bracket_sec <= 0:
            raise LiveClipCounterConfigError("bracket_sec must be positive")
        if settings.sample_stride <= 0:
            raise LiveClipCounterConfigError("sample_stride must be positive")
        if not (0 < settings.pixel_change_threshold < 1):
            raise LiveClipCounterConfigError("pixel_change_threshold must be in (0, 1)")
        if settings.min_candidate_gap_sec < 0:
            raise LiveClipCounterConfigError("min_candidate_gap_sec must be non-negative")
        if not settings.model_path:
            raise LiveClipCounterConfigError("model_path is required for clip judging")

        self._settings = settings
        self._judge_factory = judge_factory
        self._judge: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self._load_error: str | None = None
        self._counter = PlacementCounter(debounce_sec=settings.debounce_sec)
        self._pending: _PendingClip | None = None
        self._last_trigger_sec: float | None = None
        self._last_close_sec: float | None = None
        self._frame_index = 0
        self._prev_gray: Any | None = None
        self._baseline_gray: Any | None = None
        # Rolling pixel memory covering >= 2 x bracket so a judged window has
        # both before- and after-bracket pixels.
        buffer_frames = max(32, int(2 * settings.bracket_sec * 30))
        self._recent_frames: deque[tuple[float, Any]] = deque(maxlen=buffer_frames)
        self.total_count = 0

    # -- public interface ---------------------------------------------------

    def process_frame(self, frame: Any, *, source_timestamp_sec: float) -> dict[str, Any]:
        """Consume one BGR frame; returns {count, count_events, debug_payload}."""
        self._frame_index += 1
        self._remember_frame(source_timestamp_sec, frame)

        gray = None
        if frame is not None:
            gray = _to_gray(frame)

        # Open on ANY change vs the previous frame. While a window is open,
        # "busy" means changed vs the PRE-PLACEMENT BASELINE: the busy->calm
        # transition itself must read as calm, or the cooldown can never start
        # (a consecutive-frame diff flags the transition as change forever).
        triggered = False
        change_ratio = 0.0
        if gray is not None:
            if self._pending is None:
                reference = self._prev_gray
            else:
                reference = self._baseline_gray
            if reference is not None and reference.shape == gray.shape:
                change_ratio = _change_ratio(reference, gray, self._settings.roi_polygon)
                triggered = change_ratio >= self._settings.pixel_change_threshold
            self._prev_gray = gray
            if self._pending is None and not triggered:
                self._baseline_gray = gray

        count_events: list[dict[str, Any]] = []
        verdict_payload: dict[str, Any] | None = None

        if triggered:
            self._open_or_extend(source_timestamp_sec)
        elif self._pending is not None and self._cooldown_elapsed(source_timestamp_sec):
            verdict_payload, count_events = self._close_and_judge(
                quiet_sec=source_timestamp_sec
            )
            if self._pending is None:
                self._baseline_gray = gray

        if count_events:
            self.total_count = count_events[-1]["count"]

        return {
            "count": len(count_events),
            "count_events": count_events,
            "debug_payload": {
                "mode": "live_clip",
                "triggered": triggered,
                "change_ratio": round(change_ratio, 4),
                "pending_window": (
                    None
                    if self._pending is None
                    else {
                        "start_sec": round(self._pending.start_sec, 3),
                        "last_trigger_sec": round(self._pending.last_trigger_sec, 3),
                    }
                ),
                "verdict": verdict_payload,
                "total_count": self.total_count,
                "student_loaded": self._judge is not None,
                "student_load_error": self._load_error,
            },
        }

    def flush(self) -> list[dict[str, Any]]:
        """Close any open window and finalize pending placements at EOF/reset."""
        closed_events: list[dict[str, Any]] = []
        if self._pending is not None:
            _, closed_events = self._close_and_judge(
                quiet_sec=self._pending.last_trigger_sec
            )
        finalized = [
            {
                "count": event.count,
                "center_sec": round(event.center_sec, 3),
                "start_sec": round(event.start_sec, 3),
                "end_sec": round(event.end_sec, 3),
                "candidate_ids": event.candidate_ids,
            }
            for event in self._counter.finalize()
        ]
        events = [*closed_events, *finalized]
        if events:
            self.total_count = events[-1]["count"]
        return events

    def settings_snapshot(self) -> LiveClipCounterSettings:
        """Return the frozen settings this counter was built with."""
        return self._settings

    # -- internals ----------------------------------------------------------

    def _ensure_judge(self) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
        if self._judge is None and self._load_error is None:
            try:
                self._judge = self._judge_factory({"model_path": self._settings.model_path})
            except Exception as exc:  # noqa: BLE001 - runtime must survive a bad bundle
                self._load_error = f"student judge failed to load: {exc}"
                logger.error("%s", self._load_error)
        return self._judge

    def _open_or_extend(self, timestamp_sec: float) -> None:
        if (
            self._last_close_sec is not None
            and timestamp_sec - self._last_close_sec < self._settings.min_candidate_gap_sec
        ):
            return  # refractory: residual motion right after a judged close
        if self._pending is None:
            self._pending = _PendingClip(
                first_trigger_sec=timestamp_sec - self._settings.bracket_sec,
                last_trigger_sec=timestamp_sec,
            )
        else:
            self._pending.last_trigger_sec = timestamp_sec
        self._last_trigger_sec = timestamp_sec

    def _cooldown_elapsed(self, current_sec: float) -> bool:
        return (
            self._last_trigger_sec is None
            or current_sec - self._last_trigger_sec >= self._settings.cooldown_after_trigger_sec
        )

    def _close_and_judge(self, *, quiet_sec: float) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        pending = self._pending
        self._pending = None
        self._last_trigger_sec = None
        self._last_close_sec = quiet_sec
        if pending is None:
            return None, []

        end_sec = pending.end_sec(quiet_sec=quiet_sec, bracket_sec=self._settings.bracket_sec)
        center = (pending.start_sec + end_sec) / 2.0
        candidate_id = f"live-{self._frame_index:09d}"
        descriptor: dict[str, Any] = {
            "candidate_id": candidate_id,
            "start_sec": round(pending.start_sec, 3),
            "end_sec": round(end_sec, 3),
            "center_sec": round(center, 3),
            "source": "live",
            "frames_small_bgr": self._slice_buffered_frames(pending.start_sec, end_sec),
        }

        decision = "refute"
        score = 0.0
        judged_by = "no-judge"
        judge_error: str | None = None
        judge = self._ensure_judge()
        if judge is not None:
            try:
                judged = judge(descriptor)
                decision = str(judged.get("decision", "refute"))
                score = float(judged.get("score", 0.0))
                judged_by = "student"
            except Exception as exc:  # noqa: BLE001 - a bad clip must not kill the loop
                judge_error = f"student judge raised: {exc}"
                logger.error("%s", judge_error)
                judged_by = "error"

        events: list[list[Any]] = []
        events.append(
            self._emit(
                PlacementVerdict(
                    center_sec=center,
                    decision="assert" if decision == "assert" else "refute",
                    score=score,
                    candidate_id=candidate_id,
                )
            )
        )
        # The calm that closed this window IS the quiet observation; feed it so
        # an assert actually completes into a count (exam-stream parity).
        events.append(
            self._emit(PlacementVerdict(center_sec=quiet_sec, decision="refute", score=None))
        )
        flat = [event for batch in events for event in batch]
        payloads = [
            {
                "count": event.count,
                "center_sec": round(event.center_sec, 3),
                "start_sec": round(event.start_sec, 3),
                "end_sec": round(event.end_sec, 3),
                "candidate_ids": event.candidate_ids,
            }
            for event in flat
        ]
        verdict_payload = {
            "decision": decision,
            "score": round(score, 4),
            "judged_by": judged_by,
            "judge_error": judge_error,
            "candidate_id": candidate_id,
            "window_sec": [round(pending.start_sec, 3), round(end_sec, 3)],
            "quiet_sec": round(quiet_sec, 3),
        }
        return verdict_payload, payloads

    def _emit(self, verdict: PlacementVerdict) -> list[Any]:
        return self._counter.update(verdict)

    def _remember_frame(self, timestamp_sec: float, frame: Any) -> None:
        if frame is None:
            return
        import cv2
        import numpy as np

        try:
            small = cv2.resize(np.asarray(frame), (_SMALL_W, _SMALL_H))
        except Exception:  # noqa: BLE001 - unreadable frame just skips the buffer
            return
        self._recent_frames.append((float(timestamp_sec), small))

    def _slice_buffered_frames(self, start_sec: float, end_sec: float) -> list[Any]:
        picked: list[Any] = []
        stride = self._settings.sample_stride
        for index, (ts, frame) in enumerate(self._recent_frames):
            if start_sec <= ts <= end_sec and index % stride == 0:
                picked.append(frame)
        return picked

def _to_gray(frame: Any) -> Any:
    import cv2
    import numpy as np

    gray = cv2.resize(np.asarray(frame), (_SMALL_W, _SMALL_H))
    return cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)


def _change_ratio(reference: Any, gray: Any, roi_polygon: tuple[tuple[float, float], ...]) -> float:
    import numpy as np

    inside = _zone_mask(gray.shape, roi_polygon)
    changed = ((np.abs(gray.astype(int) - reference.astype(int)) > 24) & inside).sum()
    zone_cells = int(inside.sum())
    if zone_cells == 0:
        return 0.0
    return float(changed) / float(zone_cells)


def _zone_mask(shape: tuple[int, ...], roi_polygon: tuple[tuple[float, float], ...]) -> Any:
    import numpy as np

    height, width = shape[:2]
    xs = np.arange(width)
    ys = np.arange(height)
    grid_x, grid_y = np.meshgrid(xs, ys)
    points_x = grid_x / float(width)
    points_y = grid_y / float(height)
    inside = np.zeros((height, width), dtype=bool)
    count = len(roi_polygon)
    for index in range(count):
        x1, y1 = roi_polygon[index]
        x2, y2 = roi_polygon[(index + 1) % count]
        crosses = ((y1 > points_y) != (y2 > points_y)) & (
            points_x < (x2 - x1) * (points_y - y1) / ((y2 - y1) or 1e-9) + x1
        )
        inside ^= crosses
    return inside


def live_clip_counter_enabled() -> bool:
    """Track B live mode switch: FC_COUNTING_MODE=clip_student."""
    return get_counting_mode() == "clip_student"


__all__ = [
    "LiveClipCounter",
    "LiveClipCounterConfigError",
    "LiveClipCounterSettings",
    "live_clip_counter_enabled",
    "load_settings_from_env",
]
