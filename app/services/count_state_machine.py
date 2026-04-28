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
    "UNCERTAIN_REVIEW",
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
    source_token_ttl_frames: int = 45
    resident_match_center_distance: float = 30.0


@dataclass(frozen=True)
class CountEvent:
    track_id: int
    count: int
    reason: Literal["stable_in_output", "disappeared_in_output", "approved_delivery_chain"]
    bbox: Box


@dataclass
class _SourceToken:
    token_id: str
    track_id: int
    created_frame: int
    last_frame: int
    source_bbox: Box
    consumed: bool = False


@dataclass
class _ResidentObject:
    resident_id: str
    track_id: int
    bbox: Box
    center: tuple[float, float]
    matched_track_ids: set[int] = field(default_factory=set)


@dataclass
class _TrackMemory:
    track_id: int
    state: TrackLifecycleState = "NEW_TRACK"
    source_frames: int = 0
    output_frames: int = 0
    stable_output_frames: int = 0
    missing_frames: int = 0
    source_token: _SourceToken | None = None
    entered_output: bool = False
    last_valid_detection_in_output: bool = False
    has_allowed_gate_crossing: bool = False
    counted: bool = False
    last_bbox: Box | None = None
    last_center: tuple[float, float] | None = None
    last_seen_center: tuple[float, float] | None = None
    state_path: list[str] = field(default_factory=lambda: ["NEW_TRACK"])
    uncertain_reasons: list[str] = field(default_factory=list)
    approved_for_count: bool = True

    @property
    def has_source_token(self) -> bool:
        return self.source_token is not None and not self.source_token.consumed

    def set_state(self, state: TrackLifecycleState) -> None:
        if self.state != state:
            self.state = state
            self.state_path.append(state)

    def add_uncertain(self, reason: str) -> None:
        if reason not in self.uncertain_reasons:
            self.uncertain_reasons.append(reason)
        self.set_state("UNCERTAIN_REVIEW")


class CountStateMachine:
    """Conservative source-token/output-resident counter.

    Detector/tracker output is treated as evidence. Count authority stays here:
    only a non-expired source token can become one committed output resident.
    """

    def __init__(self, config: CountConfig) -> None:
        self.config = config
        self.total_count = 0
        self._frame_index = 0
        self._token_sequence = 0
        self._resident_sequence = 0
        self._tracks: dict[int, _TrackMemory] = {}
        self._residents: dict[str, _ResidentObject] = {}
        self._committed_delivery_chains: set[str] = set()

    def update(self, detections: list[TrackDetection], approved_track_ids: set[int] | None = None) -> list[CountEvent]:
        self._frame_index += 1
        events: list[CountEvent] = []
        current_ids = {detection.track_id for detection in detections}

        for detection in detections:
            track = self._tracks.setdefault(
                detection.track_id,
                _TrackMemory(track_id=detection.track_id),
            )
            track.approved_for_count = approved_track_ids is None or detection.track_id in approved_track_ids
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

        self._expire_stale_source_tokens()
        return events

    def track_state(self, track_id: int) -> TrackLifecycleState | None:
        track = self._tracks.get(track_id)
        return track.state if track is not None else None

    def track_state_path(self, track_id: int) -> list[str]:
        track = self._tracks.get(track_id)
        return list(track.state_path) if track is not None else []

    def track_uncertain_reasons(self, track_id: int) -> list[str]:
        track = self._tracks.get(track_id)
        return list(track.uncertain_reasons) if track is not None else []

    def commit_approved_delivery_chain(
        self,
        *,
        chain_id: str,
        output_track_id: int,
        output_bbox: Box,
        source_track_id: int | None = None,
    ) -> CountEvent | None:
        if chain_id in self._committed_delivery_chains:
            return None

        track = self._tracks.setdefault(output_track_id, _TrackMemory(track_id=output_track_id))
        if track.counted:
            self._committed_delivery_chains.add(chain_id)
            return None

        track.last_bbox = output_bbox
        track.last_center = box_center(output_bbox)
        track.last_seen_center = track.last_center
        track.entered_output = True
        track.last_valid_detection_in_output = True
        track.approved_for_count = True
        track.has_allowed_gate_crossing = True
        track.source_frames = max(track.source_frames, self.config.source_min_frames)
        track.output_frames = max(track.output_frames, 1)
        if track.state == "NEW_TRACK":
            track.set_state("OBSERVING")
        track.set_state("IN_OUTPUT_UNSETTLED")

        source_track = self._tracks.get(source_track_id) if source_track_id is not None else None
        if source_track is not None and source_track.source_token is not None and not source_track.source_token.consumed:
            track.source_token = source_track.source_token
            track.source_token.track_id = output_track_id
            track.source_token.last_frame = self._frame_index
        elif track.source_token is None:
            track.source_token = self._create_source_token(track, output_bbox)

        self._committed_delivery_chains.add(chain_id)
        return self._commit_count(track, "approved_delivery_chain")

    def _update_track(self, track: _TrackMemory, detection: TrackDetection) -> CountEvent | None:
        membership = zone_membership(detection.bbox, self.config.zones)
        current_center = box_center(detection.bbox)
        previous_seen_center = track.last_seen_center

        track.missing_frames = 0
        track.last_bbox = detection.bbox
        track.last_center = current_center
        track.last_seen_center = current_center
        if track.source_token is not None and not track.source_token.consumed:
            track.source_token.last_frame = self._frame_index

        if membership.ignore_overlap >= self.config.ignore_overlap_threshold:
            track.last_valid_detection_in_output = False
            return None

        source_hit = membership.source_overlap >= self.config.source_overlap_threshold
        output_hit = membership.output_overlap >= self.config.output_overlap_threshold
        track.last_valid_detection_in_output = output_hit

        if track.state == "NEW_TRACK":
            resident = self._matching_resident(current_center)
            if resident is not None and output_hit:
                resident.matched_track_ids.add(track.track_id)
                track.set_state("RESIDENT_OUTPUT_OBJECT")
                return None
            if output_hit and not source_hit:
                inherited = self._inherit_source_token_for_new_track(track, detection.bbox)
                if inherited is None:
                    track.set_state("RESIDENT_OUTPUT_OBJECT")
                    return None
            track.set_state("OBSERVING")

        if source_hit and not track.counted and track.state != "RESIDENT_OUTPUT_OBJECT":
            track.source_frames += 1
            if track.source_frames >= self.config.source_min_frames and not track.has_source_token:
                track.source_token = self._create_source_token(track, detection.bbox)
                track.set_state("SOURCE_CONFIRMED")

        if self._crossed_gate_allowed(previous_seen_center, current_center):
            track.has_allowed_gate_crossing = True
            if track.has_source_token and track.state == "SOURCE_CONFIRMED":
                track.set_state("MOVING_TO_OUTPUT")

        if output_hit:
            track.output_frames += 1
            if track.has_source_token and not self._gate_requirement_satisfied(track):
                track.add_uncertain("missing_gate_crossing")
                return None
            if track.has_source_token and self._gate_requirement_satisfied(track):
                track.entered_output = True
                if track.state in ("SOURCE_CONFIRMED", "MOVING_TO_OUTPUT", "OBSERVING", "UNCERTAIN_REVIEW"):
                    track.set_state("IN_OUTPUT_UNSETTLED")
                if self._is_stable(previous_seen_center, current_center):
                    track.stable_output_frames += 1
                else:
                    track.stable_output_frames = 1
                if self._can_count_track(track) and track.stable_output_frames >= self.config.output_stable_frames:
                    return self._commit_count(track, "stable_in_output")
            elif not track.has_source_token and not track.counted:
                track.set_state("RESIDENT_OUTPUT_OBJECT")
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
            and track.approved_for_count
            and not track.counted
            and track.last_bbox is not None
            and track.missing_frames >= self.config.disappear_in_output_frames
        ):
            return self._commit_count(track, "disappeared_in_output")
        return None

    def _commit_count(
        self,
        track: _TrackMemory,
        reason: Literal["stable_in_output", "disappeared_in_output", "approved_delivery_chain"],
    ) -> CountEvent:
        track.counted = True
        if track.source_token is not None:
            track.source_token.consumed = True
        track.set_state("COUNTED_OUTPUT_RESIDENT")
        self.total_count += 1
        assert track.last_bbox is not None
        self._resident_sequence += 1
        resident = _ResidentObject(
            resident_id=f"resident-{self._resident_sequence}",
            track_id=track.track_id,
            bbox=track.last_bbox,
            center=box_center(track.last_bbox),
            matched_track_ids={track.track_id},
        )
        self._residents[resident.resident_id] = resident
        return CountEvent(
            track_id=track.track_id,
            count=1,
            reason=reason,
            bbox=track.last_bbox,
        )

    def _create_source_token(self, track: _TrackMemory, bbox: Box) -> _SourceToken:
        self._token_sequence += 1
        return _SourceToken(
            token_id=f"source-token-{self._token_sequence}",
            track_id=track.track_id,
            created_frame=self._frame_index,
            last_frame=self._frame_index,
            source_bbox=bbox,
        )

    def _inherit_source_token_for_new_track(self, track: _TrackMemory, bbox: Box) -> _SourceToken | None:
        candidates = [
            candidate
            for candidate in self._tracks.values()
            if candidate.track_id != track.track_id
            and candidate.has_source_token
            and not candidate.counted
            and self._token_age(candidate) <= self.config.source_token_ttl_frames
        ]
        if not candidates:
            return None
        source_track = min(candidates, key=lambda candidate: candidate.missing_frames)
        token = source_track.source_token
        if token is None:
            return None
        track.source_token = token
        token.track_id = track.track_id
        token.last_frame = self._frame_index
        track.source_frames = max(track.source_frames, self.config.source_min_frames)
        if source_track.has_allowed_gate_crossing:
            track.has_allowed_gate_crossing = True
        track.set_state("SOURCE_CONFIRMED")
        return token

    def _expire_stale_source_tokens(self) -> None:
        for track in self._tracks.values():
            if not track.has_source_token or track.entered_output or track.counted:
                continue
            if self._token_age(track) > self.config.source_token_ttl_frames:
                assert track.source_token is not None
                track.source_token.consumed = True
                track.add_uncertain("token_expired_before_output")

    def _token_age(self, track: _TrackMemory) -> int:
        if track.source_token is None:
            return 0
        return self._frame_index - track.source_token.last_frame

    def _matching_resident(self, center: tuple[float, float]) -> _ResidentObject | None:
        best: tuple[float, _ResidentObject] | None = None
        for resident in self._residents.values():
            distance = self._distance(center, resident.center)
            if distance <= self.config.resident_match_center_distance:
                if best is None or distance < best[0]:
                    best = (distance, resident)
        return best[1] if best is not None else None

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
        return track.has_source_token and track.approved_for_count and self._gate_requirement_satisfied(track) and not track.counted

    def _is_stable(
        self,
        previous_center: tuple[float, float] | None,
        current_center: tuple[float, float],
    ) -> bool:
        if previous_center is None:
            return False
        return self._distance(previous_center, current_center) <= self.config.stable_center_epsilon

    def _distance(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5
