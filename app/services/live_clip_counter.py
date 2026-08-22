"""Live Track B counting: per-frame zone trigger -> buffered clip candidates ->
student judge -> debounced placement counts (ADR-0004).

This module is the deep seam between the frame-paced VisionWorker loop and the
exam kernel's counting machinery (app.services.exam_gate /
app.services.placement_counter). The runtime owns no ML logic; it feeds frames
and timestamps into one interface and receives count events plus debug payload.

Design notes:
- The zone trigger is deliberately dumb and high-recall (pixel change on the
  output zone), mirroring scripts/record_stream_segments.py-era tripwire
  semantics: flag every candidate, let the student be the precision filter.
- Clip windows are buffered as center_sec + bracket_sec spans. The judge is
  called with a *clip descriptor* dict, not raw video: production supplies a
  judge that renders/crops buffered frames to tensors
  (app.services.clip_models.load_student_judge consumes extracted clips);
  tests inject a fake judge over synthetic descriptors.
- Counting reuses PlacementCounter's quiet -> placement -> quiet debounce so a
  live session and the blind exam share one state machine.
- Nothing here mutates the runtime total directly: VisionWorker stays the
  system of record and records what this module emits (ADR-0001/0005).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.settings import get_counting_mode
from app.services.placement_counter import PlacementCounter, PlacementVerdict

logger = logging.getLogger(__name__)

STUDENT_JUDGE_FACTORY = Callable[[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]


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


@dataclass
class _PendingClip:
    start_sec: float
    end_sec: float
    frame_indices: list[int] = field(default_factory=list)


def load_settings_from_env() -> LiveClipCounterSettings:
    """Read live Track B settings from FC_CLIP_* environment variables."""
    import os

    def _float(name: str, default: float) -> float:
        raw = os.getenv(name)
        return default if not raw else float(raw)

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        return default if not raw else int(raw)

    return LiveClipCounterSettings(
        model_path=os.getenv("FC_CLIP_STUDENT_MODEL_PATH", ""),
        bracket_sec=_float("FC_CLIP_BRACKET_SEC", 8.0),
        sample_stride=_int("FC_CLIP_SAMPLE_STRIDE", 3),
        pixel_change_threshold=_float("FC_CLIP_PIXEL_CHANGE_THRESHOLD", 0.02),
        min_candidate_gap_sec=_float("FC_CLIP_MIN_CANDIDATE_GAP_SEC", 1.0),
        cooldown_after_trigger_sec=_float("FC_CLIP_COOLDOWN_SEC", 16.0),
        debounce_sec=_float("FC_CLIP_DEBOUNCE_SEC", 25.0),
    )


class LiveClipCounter:
    """Per-frame Track B counter owned by VisionWorker when enabled.

    Interface (the whole point of this module):

        counter = LiveClipCounter(settings=..., judge_factory=torch_judge_loader)
        result = counter.process_frame(frame_bgr, source_timestamp_sec=ts)
        if result.count_events:
            ...record them / bump the audited runtime total...
        result.debug_payload  # for the dashboard overlay

    One class, three methods, no leaked internals.
    """

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
        if not settings.model_path:
            raise LiveClipCounterConfigError("model_path is required for clip judging")

        self._settings = settings
        self._judge_factory = judge_factory
        self._judge: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self._load_error: str | None = None
        self._counter = PlacementCounter(debounce_sec=settings.debounce_sec)
        self._pending_clip: _PendingClip | None = None
        self._last_trigger_center_sec: float | None = None
        self._frame_index = 0
        self._prev_small: list[list[int]] | None = None
        self.total_count = 0

    # -- public interface ---------------------------------------------------

    def process_frame(self, frame: Any, *, source_timestamp_sec: float) -> dict[str, Any]:
        """Consume one BGR frame; returns {count, count_events, debug_payload}."""
        self._frame_index += 1
        triggered = False
        change_ratio = 0.0
        if frame is not None:
            change_ratio = self._zone_change_ratio(frame)
            triggered = change_ratio >= self._settings.pixel_change_threshold

        count_events: list[dict[str, Any]] = []
        verdict_payload: dict[str, Any] | None = None

        if triggered:
            self._open_or_extend_clip(source_timestamp_sec)
        elif self._pending_clip is not None and self._clip_cooldown_elapsed(source_timestamp_sec):
            verdict_payload, count_events = self._finalize_pending_clip()

        if count_events:
            self.total_count = count_events[-1]["count"]

        return {
            "count": len(count_events),
            "count_events": count_events,
            "debug_payload": {
                "mode": "live_clip",
                "triggered": triggered,
                "change_ratio": round(change_ratio, 4),
                "pending_clip": (
                    None
                    if self._pending_clip is None
                    else {"start_sec": self._pending_clip.start_sec, "end_sec": self._pending_clip.end_sec}
                ),
                "verdict": verdict_payload,
                "total_count": self.total_count,
                "student_loaded": self._judge is not None,
                "student_load_error": self._load_error,
            },
        }

    def flush(self) -> list[dict[str, Any]]:
        """Emit any pending placement when the stream ends (EOF/hour rollover)."""
        if self._pending_clip is not None:
            self._finalize_pending_clip()
        finalized = self._counter.finalize()
        if finalized:
            self.total_count = finalized[-1].count
        return [
            {
                "count": event.count,
                "center_sec": round(event.center_sec, 3),
                "start_sec": round(event.start_sec, 3),
                "end_sec": round(event.end_sec, 3),
                "candidate_ids": event.candidate_ids,
            }
            for event in finalized
        ]

    # -- internals ----------------------------------------------------------

    def _ensure_judge(self) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
        if self._judge is None and self._load_error is None:
            try:
                self._judge = self._judge_factory({"model_path": self._settings.model_path})
            except Exception as exc:  # noqa: BLE001 - runtime must survive a bad bundle
                self._load_error = f"student judge failed to load: {exc}"
                logger.error("%s", self._load_error)
        return self._judge

    def _zone_change_ratio(self, frame: Any) -> float:
        small = _downscaled_gray(frame)
        if self._prev_small is None or len(small) != len(self._prev_small) or len(small[0]) != len(self._prev_small[0]):
            self._prev_small = small
            return 0.0
        changed = sum(
            1
            for row_index, row in enumerate(small)
            for col_index, value in enumerate(row)
            if abs(value - self._prev_small[row_index][col_index]) > 24
        )
        self._prev_small = small
        total = len(small) * len(small[0])
        return changed / float(total)

    def _open_or_extend_clip(self, timestamp_sec: float) -> None:
        if self._pending_clip is None:
            half_bracket = self._settings.bracket_sec / 2.0
            self._pending_clip = _PendingClip(
                start_sec=max(0.0, timestamp_sec - half_bracket),
                end_sec=timestamp_sec,
            )
            self._last_trigger_center_sec = timestamp_sec
        else:
            # Extend the window while the zone keeps changing; the clip is
            # judged only after the scene has been calm for a full cooldown.
            self._pending_clip.end_sec = timestamp_sec
            self._last_trigger_center_sec = timestamp_sec

    def _clip_cooldown_elapsed(self, current_sec: float) -> bool:
        last_trigger = self._last_trigger_center_sec
        if last_trigger is None:
            return True
        return current_sec - last_trigger >= self._settings.cooldown_after_trigger_sec

    def _finalize_pending_clip(
        self,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        pending = self._pending_clip
        self._pending_clip = None
        self._last_trigger_center_sec = None
        if pending is None:
            return None, []
        center_sec = (pending.start_sec + pending.end_sec) / 2.0
        descriptor = {
            "candidate_id": f"live-{self._frame_index:09d}",
            "start_sec": pending.start_sec,
            "end_sec": pending.end_sec,
            "center_sec": center_sec,
            "source": "live",
        }
        judge = self._ensure_judge()
        decision = "refute"
        score = 0.0
        judged_by = "no-judge"
        if judge is not None:
            judged = judge(descriptor)
            decision = str(judged.get("decision", "refute"))
            score = float(judged.get("score", 0.0))
            judged_by = "student"
        verdict = PlacementVerdict(
            center_sec=center_sec,
            decision="assert" if decision == "assert" else "refute",
            score=score,
            candidate_id=str(descriptor["candidate_id"]),
        )
        events = self._counter.update(verdict)
        payloads = [
            {
                "count": event.count,
                "center_sec": round(event.center_sec, 3),
                "start_sec": round(event.start_sec, 3),
                "end_sec": round(event.end_sec, 3),
                "candidate_ids": event.candidate_ids,
            }
            for event in events
        ]
        verdict_payload = {
            "decision": decision,
            "score": round(score, 4),
            "judged_by": judged_by,
            "candidate_id": descriptor["candidate_id"],
            "window_sec": [round(pending.start_sec, 3), round(pending.end_sec, 3)],
        }
        return verdict_payload, payloads


def _downscaled_gray(frame: Any, target_w: int = 64, target_h: int = 36) -> list[list[int]]:
    import cv2
    import numpy as np

    small = cv2.resize(np.asarray(frame), (target_w, target_h))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return np.asarray(gray).tolist()


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
