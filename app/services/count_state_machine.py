from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.services.calibration import (
    Box,
    CalibrationZones,
    Gate,
    box_center,
    gate_crossed_allowed_direction,
    zone_membership,
)

TrackLifecycleState = Literal[
    "NEW_TRACK",
    "OBSERVING",
    "SOURCE_CONFIRMED",
    "MOVING_TO_OUTPUT",
    "IN_OUTPUT_UNSETTLED",
    "COUNTED_OUTPUT_RESIDENT",
    "RESIDENT_OUTPUT_OBJECT",
]


@dataclass(frozen=True)
class TrackDetection:
    track_id: int
    bbox: Box
    confidence: float = 1.0


@dataclass(frozen=True)
class CountConfig:
    zones: CalibrationZones
    gate: Gate | None = None
    source_min_frames: int = 3
    output_stable_frames: int = 3
    source_overlap_threshold: float = 0.3
    output_overlap_threshold: float = 0.4
    ignore_overlap_threshold: float = 0.5
    resident_output_overlap_threshold: float = 0.4
    stable_center_epsilon: float = 5.0
    disappear_in_output_frames: int = 2
    max_missing_frames: int = 30


@dataclass(frozen=True)
class CountEvent:
    track_id: int
    count: int
    reason: Literal["stable_in_output", "disappeared_in_output"]
    bbox: Box


@dataclass
class _TrackMemory:
    track_id: int
    state: TrackLifecycleState = "NEW_TRACK"
    source_frames: int = 0
    output_frames: int = 0
    stable_output_frames: int = 0
    missing_frames: int = 0
    has_source_token: bool = False
    entered_output: bool = False
    last_valid_detection_in_output: bool = False
    has_allowed_gate_crossing: bool = False
    counted: bool = False
    last_bbox: Box | None = None
    last_center: tuple[float, float] | None = None
    last_seen_center: tuple[float, float] | None = None


class CountStateMachine:
    """Conservative source-token/output-resident counter.

    This module intentionally accepts already-tracked detections. Detector and
    tracker quality are inputs; count authority stays here.
    """

    def __init__(self, config: CountConfig) -> None:
        self.config = config
        self.total_count = 0
        self._tracks: dict[int, _TrackMemory] = {}
        self._resident_track_ids: set[int] = set()

    def update(self, detections: list[TrackDetection]) -> list[CountEvent]:
        events: list[CountEvent] = []
        current_ids = {detection.track_id for detection in detections}

        for detection in detections:
            track = self._tracks.setdefault(
                detection.track_id,
                _TrackMemory(track_id=detection.track_id),
            )
            event = self._update_track(track, detection)
            if event is not None:
                events.append(event)

        for track_id, track in list(self._tracks.items()):
            if track_id in current_ids:
                continue
            event = self._mark_missing(track)
            if event is not None:
                events.append(event)
            if track.missing_frames > self.config.max_missing_frames:
                del self._tracks[track_id]

        return events

    def _update_track(self, track: _TrackMemory, detection: TrackDetection) -> CountEvent | None:
        membership = zone_membership(detection.bbox, self.config.zones)
        current_center = box_center(detection.bbox)
        previous_seen_center = track.last_seen_center

        track.missing_frames = 0
        track.last_bbox = detection.bbox
        track.last_center = current_center
        track.last_seen_center = current_center

        if membership.ignore_overlap >= self.config.ignore_overlap_threshold:
            track.last_valid_detection_in_output = False
            return None

        source_hit = membership.source_overlap >= self.config.source_overlap_threshold
        output_hit = membership.output_overlap >= self.config.output_overlap_threshold
        track.last_valid_detection_in_output = output_hit

        if track.state == "NEW_TRACK":
            if membership.output_overlap >= self.config.resident_output_overlap_threshold and not source_hit:
                track.state = "RESIDENT_OUTPUT_OBJECT"
                self._resident_track_ids.add(track.track_id)
                return None
            track.state = "OBSERVING"

        if source_hit and not track.counted and track.state != "RESIDENT_OUTPUT_OBJECT":
            track.source_frames += 1
            if track.source_frames >= self.config.source_min_frames:
                track.has_source_token = True
                track.state = "SOURCE_CONFIRMED"

        if self._crossed_gate_allowed(previous_seen_center, current_center):
            track.has_allowed_gate_crossing = True
            if track.has_source_token and track.state == "SOURCE_CONFIRMED":
                track.state = "MOVING_TO_OUTPUT"

        if output_hit:
            track.output_frames += 1
            if self._can_count_track(track):
                track.entered_output = True
                if track.state in ("SOURCE_CONFIRMED", "MOVING_TO_OUTPUT", "OBSERVING"):
                    track.state = "IN_OUTPUT_UNSETTLED"
                if self._is_stable(previous_seen_center, current_center):
                    track.stable_output_frames += 1
                else:
                    track.stable_output_frames = 1
                if track.stable_output_frames >= self.config.output_stable_frames:
                    return self._commit_count(track, "stable_in_output")
            elif not track.has_source_token and not track.counted:
                track.state = "RESIDENT_OUTPUT_OBJECT"
                self._resident_track_ids.add(track.track_id)
        else:
            track.output_frames = 0
            track.stable_output_frames = 0

        return None

    def _mark_missing(self, track: _TrackMemory) -> CountEvent | None:
        track.missing_frames += 1
        if (
            track.has_source_token
            and track.entered_output
            and track.last_valid_detection_in_output
            and self._gate_requirement_satisfied(track)
            and not track.counted
            and track.last_bbox is not None
            and track.missing_frames >= self.config.disappear_in_output_frames
        ):
            return self._commit_count(track, "disappeared_in_output")
        return None

    def _commit_count(
        self,
        track: _TrackMemory,
        reason: Literal["stable_in_output", "disappeared_in_output"],
    ) -> CountEvent:
        track.counted = True
        track.has_source_token = False
        track.state = "COUNTED_OUTPUT_RESIDENT"
        self._resident_track_ids.add(track.track_id)
        self.total_count += 1
        assert track.last_bbox is not None
        return CountEvent(
            track_id=track.track_id,
            count=1,
            reason=reason,
            bbox=track.last_bbox,
        )

    def _crossed_gate_allowed(
        self,
        previous_center: tuple[float, float] | None,
        current_center: tuple[float, float],
    ) -> bool:
        if self.config.gate is None or previous_center is None:
            return False
        return gate_crossed_allowed_direction(previous_center, current_center, self.config.gate)

    def _gate_requirement_satisfied(self, track: _TrackMemory) -> bool:
        return self.config.gate is None or track.has_allowed_gate_crossing

    def _can_count_track(self, track: _TrackMemory) -> bool:
        return track.has_source_token and self._gate_requirement_satisfied(track) and not track.counted

    def _is_stable(
        self,
        previous_center: tuple[float, float] | None,
        current_center: tuple[float, float],
    ) -> bool:
        if previous_center is None:
            return False
        dx = current_center[0] - previous_center[0]
        dy = current_center[1] - previous_center[1]
        return (dx * dx + dy * dy) ** 0.5 <= self.config.stable_center_epsilon
