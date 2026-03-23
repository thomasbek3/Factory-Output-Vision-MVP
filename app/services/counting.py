from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Track:
    track_id: int
    centroid: tuple[int, int]
    first_centroid: tuple[int, int]
    previous_centroid: tuple[int, int] | None
    age: int
    frames_seen: int
    last_side: int | None
    counted: bool


@dataclass
class DetectedObject:
    centroid: tuple[int, int]
    bbox: tuple[int, int, int, int]
    area: float


@dataclass
class DetectionDebugResult:
    detections: list[DetectedObject]
    foreground_mask: np.ndarray


class YoloObjectDetector:
    """YOLO-based object detector for counting pipeline.

    Replaces blob/bg-subtraction detection with proper ML inference.
    Excludes person detections by default so human hands/bodies
    don't get counted as factory output.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.3,
        excluded_classes: list[int] | None = None,
    ) -> None:
        from ultralytics import YOLO

        self._model = YOLO(model_path)
        self._conf_threshold = conf_threshold
        # Default: exclude class 0 (person) so hands/arms don't count
        self._excluded_classes = excluded_classes if excluded_classes is not None else [0]

    def detect(self, frame: np.ndarray) -> DetectionDebugResult:
        results = self._model.predict(
            source=frame,
            conf=self._conf_threshold,
            device="cpu",
            verbose=False,
        )

        detections: list[DetectedObject] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                if cls_id in self._excluded_classes:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x, y = int(x1), int(y1)
                w, h = max(0, int(x2 - x1)), max(0, int(y2 - y1))
                cx = x + w // 2
                cy = y + h // 2
                area = float(w * h)
                detections.append(
                    DetectedObject(
                        centroid=(cx, cy),
                        bbox=(x, y, w, h),
                        area=area,
                    )
                )

        # Create a simple visualization mask from the detections
        h_frame, w_frame = frame.shape[:2]
        mask = np.zeros((h_frame, w_frame), dtype=np.uint8)
        for det in detections:
            bx, by, bw, bh = det.bbox
            cv2.rectangle(mask, (bx, by), (bx + bw, by + bh), 255, -1)

        return DetectionDebugResult(detections=detections, foreground_mask=mask)

    def detect_people(self, frame: np.ndarray) -> list[dict[str, int | float]]:
        """Detect only people (class 0) — used for person-ignore masking."""
        results = self._model.predict(
            source=frame,
            conf=self._conf_threshold,
            classes=[0],
            device="cpu",
            verbose=False,
        )
        detections: list[dict[str, int | float]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                x, y = int(x1), int(y1)
                w, h = max(0, int(x2 - x1)), max(0, int(y2 - y1))
                detections.append(
                    {"x": x, "y": y, "w": w, "h": h, "confidence": conf}
                )
        return detections


class CentroidTracker:
    def __init__(self, max_age_frames: int, max_match_distance: float) -> None:
        self.max_age_frames = max_age_frames
        self.max_match_distance = max_match_distance
        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    @property
    def tracks(self) -> dict[int, Track]:
        return self._tracks

    def update(self, centroids: list[tuple[int, int]]) -> dict[int, Track]:
        """Update tracks with new centroids. Returns active tracks.

        Dead tracks (age > max_age_frames) are removed automatically.
        Use update_with_dead() instead if you need to inspect dead tracks.
        """
        _, active = self._do_update(centroids)
        return active

    def update_with_dead(self, centroids: list[tuple[int, int]]) -> tuple[list[Track], dict[int, Track]]:
        """Update tracks and return (dead_tracks, active_tracks).

        Dead tracks are tracks that exceeded max_age_frames this update.
        They are removed from internal state but returned for inspection
        (e.g., event_based mode counts tracks that die after enough frames).
        """
        return self._do_update(centroids)

    def _do_update(self, centroids: list[tuple[int, int]]) -> tuple[list[Track], dict[int, Track]]:
        assigned_detections: set[int] = set()
        updated_ids: set[int] = set()
        dead_tracks: list[Track] = []

        for track_id, track in list(self._tracks.items()):
            best_idx = -1
            best_dist = float("inf")
            for idx, centroid in enumerate(centroids):
                if idx in assigned_detections:
                    continue
                dist = np.linalg.norm(np.array(track.centroid) - np.array(centroid))
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx

            if best_idx >= 0 and best_dist <= self.max_match_distance:
                self._tracks[track_id].previous_centroid = self._tracks[track_id].centroid
                self._tracks[track_id].centroid = centroids[best_idx]
                self._tracks[track_id].age = 0
                self._tracks[track_id].frames_seen += 1
                assigned_detections.add(best_idx)
                updated_ids.add(track_id)
            else:
                self._tracks[track_id].age += 1
                if self._tracks[track_id].age > self.max_age_frames:
                    dead_tracks.append(self._tracks[track_id])
                    del self._tracks[track_id]

        for idx, centroid in enumerate(centroids):
            if idx in assigned_detections:
                continue
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = Track(
                track_id=track_id,
                centroid=centroid,
                first_centroid=centroid,
                previous_centroid=None,
                age=0,
                frames_seen=1,
                last_side=None,
                counted=False,
            )

        return dead_tracks, self._tracks


class CounterState:
    def __init__(self) -> None:
        now = datetime.now()
        self.minute_key = (now.year, now.month, now.day, now.hour, now.minute)
        self.hour_key = (now.year, now.month, now.day, now.hour)
        self.counts_this_minute = 0
        self.counts_this_hour = 0

    def rollover_if_needed(self) -> None:
        now = datetime.now()
        minute_key = (now.year, now.month, now.day, now.hour, now.minute)
        hour_key = (now.year, now.month, now.day, now.hour)
        if minute_key != self.minute_key:
            self.minute_key = minute_key
            self.counts_this_minute = 0
        if hour_key != self.hour_key:
            self.hour_key = hour_key
            self.counts_this_hour = 0

    def increment(self) -> None:
        self.rollover_if_needed()
        self.counts_this_minute += 1
        self.counts_this_hour += 1


def apply_roi_mask(frame: np.ndarray, roi_polygon: list[dict[str, float]] | None) -> np.ndarray:
    if not roi_polygon or len(roi_polygon) < 3:
        return frame
    h, w = frame.shape[:2]
    pts = np.array([[int(p["x"] * w), int(p["y"] * h)] for p in roi_polygon], dtype=np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    return cv2.bitwise_and(frame, frame, mask=mask)


def count_new_tracks(
    tracks: dict[int, Track],
    *,
    min_track_frames: int = 5,
) -> int:
    """Count tracks that have been confirmed (seen enough frames).

    Each track counts at most once (track.counted flag).
    This replaces the old line-crossing counter — instead of requiring
    objects to cross a line, we count unique new objects that persist
    in the output zone long enough to be real.
    """
    count = 0
    for track in tracks.values():
        if track.counted:
            continue
        if track.frames_seen >= min_track_frames:
            track.counted = True
            count += 1
    return count


class EventBasedCounter:
    """Counts carry events from continuous YOLO detections.

    A carry event = a cluster of consecutive frames with detections.
    When detections stop for > gap_seconds, the event ends.
    Events shorter than min_duration_seconds are filtered as flicker.
    Each valid event = +1 count.
    """

    def __init__(
        self,
        gap_seconds: float = 3.0,
        min_duration_seconds: float = 2.0,
    ) -> None:
        self.gap_seconds = gap_seconds
        self.min_duration_seconds = min_duration_seconds

        self._event_start_ts: float | None = None
        self._last_detection_ts: float | None = None
        self._pending_event_counted = False

    def update(self, has_detections: bool, now: float | None = None) -> int:
        """Call each frame. Returns count increment (0 or 1).

        Args:
            has_detections: True if YOLO found any objects this frame.
            now: Current timestamp (defaults to time.time()).

        Returns:
            1 if a carry event just completed and is valid, else 0.
        """
        import time as _time

        if now is None:
            now = _time.time()

        increment = 0

        if has_detections:
            if self._event_start_ts is None:
                # Start new event
                self._event_start_ts = now
                self._pending_event_counted = False
            self._last_detection_ts = now
        else:
            # No detections this frame — check if an event just ended
            if self._event_start_ts is not None and self._last_detection_ts is not None:
                gap = now - self._last_detection_ts
                if gap >= self.gap_seconds and not self._pending_event_counted:
                    # Event ended. Check duration.
                    duration = self._last_detection_ts - self._event_start_ts
                    if duration >= self.min_duration_seconds:
                        increment = 1
                    self._pending_event_counted = True
                    self._event_start_ts = None
                    self._last_detection_ts = None

        return increment

    def reset(self) -> None:
        self._event_start_ts = None
        self._last_detection_ts = None
        self._pending_event_counted = False


def count_dead_tracks(
    dead_tracks: list[Track],
    *,
    min_track_frames: int = 8,
) -> int:
    """Count dead tracks that lived long enough to be real objects.

    Used in event_based mode: when a panel-in-transit disappears (worker
    placed it down / left the frame), the track dies → +1 count, provided
    the track existed for >= min_track_frames to filter false positives.

    Args:
        dead_tracks: Tracks that just died (from CentroidTracker.update_with_dead).
        min_track_frames: Minimum frames the track must have been seen.

    Returns the number of qualifying dead tracks.
    """
    count = 0
    for track in dead_tracks:
        if track.frames_seen >= min_track_frames:
            count += 1
            logger.info(
                "EVENT_TRACK_DIED: track_id=%d, frames_seen=%d → +1 count",
                track.track_id, track.frames_seen,
            )
        else:
            logger.debug(
                "EVENT_TRACK_DIED_SHORT: track_id=%d, frames_seen=%d (min=%d) → filtered",
                track.track_id, track.frames_seen, min_track_frames,
            )
    return count


def mark_all_tracks_counted(tracks: dict[int, Track]) -> None:
    """Mark all existing tracks as already counted (warmup).

    Called when monitoring or calibration starts so that objects
    already visible in the output zone don't get counted as new output.
    """
    for track in tracks.values():
        track.counted = True
