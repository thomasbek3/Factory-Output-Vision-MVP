from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import json
import numpy as np

from app.services.calibration import Box, CalibrationZones, Gate, box_center, zone_membership
from app.services.count_state_machine import CountConfig, CountEvent, CountStateMachine, TrackDetection
from app.services.person_panel_crop_classifier import summarize_panel_box_crop
from app.services.perception_gate import GateConfig, GateDecision, GateTrackFeatures, evaluate_track
from scripts.analyze_person_panel_separation import analyze_frame_person_panel_separation

SeparationAnalyzer = Callable[..., dict[str, Any]]
CropClassifier = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class RuntimeFrameResult:
    events: list[CountEvent]
    gate_decisions: dict[int, GateDecision]
    tracks: list[TrackDetection]


@dataclass
class _SimpleTrack:
    track_id: int
    center: tuple[float, float]
    bbox: Box
    missing_frames: int = 0
    metadata: dict[str, Any] | None = None


@dataclass
class _TrackGateAccumulator:
    track_id: int
    zones: CalibrationZones
    first_zone: str = "outside"
    last_zone: str = "outside"
    source_frames: int = 0
    output_frames: int = 0
    zones_seen: list[str] = field(default_factory=list)
    centers: list[tuple[float, float]] = field(default_factory=list)
    detections: int = 0
    max_displacement: float = 0.0
    person_overlap_ratio: float = 0.0
    outside_person_ratio: float = 1.0
    static_stack_overlap_ratio: float = 0.0
    first_seen_frame_index: int = -1
    last_seen_frame_index: int = -1

    def update(self, detection: TrackDetection, metadata: dict[str, Any] | None = None, frame_index: int = 0) -> None:
        metadata = metadata or {}
        membership = zone_membership(detection.bbox, self.zones)
        zone = "outside"
        source_active = membership.source_overlap >= 0.25
        output_active = membership.output_overlap >= 0.25
        if source_active and output_active:
            if membership.output_overlap > membership.source_overlap:
                zone = "output"
                self.output_frames += 1
            elif membership.source_overlap > membership.output_overlap:
                zone = "source"
                self.source_frames += 1
            elif membership.center_in_output and not membership.center_in_source:
                zone = "output"
                self.output_frames += 1
            else:
                zone = "source"
                self.source_frames += 1
        elif source_active:
            zone = "source"
            self.source_frames += 1
        elif output_active:
            zone = "output"
            self.output_frames += 1
        self.last_zone = zone
        if self.detections == 0:
            self.first_zone = zone
            self.first_seen_frame_index = frame_index
        if zone not in self.zones_seen:
            self.zones_seen.append(zone)
        center = box_center(detection.bbox)
        if self.centers:
            first = self.centers[0]
            self.max_displacement = max(self.max_displacement, _distance(first, center))
        self.centers.append(center)
        self.detections += 1
        self.last_seen_frame_index = frame_index
        self.person_overlap_ratio = max(self.person_overlap_ratio, float(metadata.get("person_overlap_ratio", 0.0)))
        self.outside_person_ratio = min(self.outside_person_ratio, float(metadata.get("outside_person_ratio", 1.0)))
        self.static_stack_overlap_ratio = max(
            self.static_stack_overlap_ratio,
            float(metadata.get("static_stack_overlap_ratio", metadata.get("static_overlap_ratio", 0.0))),
        )

    def to_features(self, separation: Optional["_LiveSeparationSummary"] = None) -> GateTrackFeatures:
        step_distances = [_distance(a, b) for a, b in zip(self.centers, self.centers[1:])]
        max_step = max(step_distances) if step_distances else 0.0
        mean_step = sum(step_distances) / len(step_distances) if step_distances else 0.0
        static_frames = sum(1 for center in self.centers if self.centers and _distance(self.centers[0], center) < 3.0)
        static_location_ratio = static_frames / len(self.centers) if self.centers else 0.0
        return GateTrackFeatures(
            track_id=self.track_id,
            source_frames=self.source_frames,
            output_frames=self.output_frames,
            zones_seen=list(self.zones_seen),
            first_zone=self.first_zone,
            max_displacement=self.max_displacement,
            mean_internal_motion=mean_step,
            max_internal_motion=max_step,
            detections=self.detections,
            person_overlap_ratio=self.person_overlap_ratio,
            outside_person_ratio=self.outside_person_ratio,
            static_stack_overlap_ratio=self.static_stack_overlap_ratio,
            static_location_ratio=static_location_ratio,
            flow_coherence=1.0 if max_step > 0 else 0.0,
            person_panel_recommendation=separation.recommendation if separation is not None else None,
            person_panel_total_candidate_frames=separation.total_candidate_frames if separation is not None else 0,
            person_panel_source_candidate_frames=separation.source_candidate_frames if separation is not None else 0,
            person_panel_max_visible_nonperson_ratio=separation.max_visible_ratio if separation is not None else 0.0,
            person_panel_max_signal=separation.max_signal if separation is not None else 0.0,
            person_panel_crop_recommendation=separation.crop_recommendation if separation is not None else None,
            person_panel_crop_positive_crops=separation.crop_positive_frames if separation is not None else 0,
            person_panel_crop_negative_crops=separation.crop_negative_frames if separation is not None else 0,
            person_panel_crop_total_crops=separation.crop_total_frames if separation is not None else 0,
            person_panel_crop_positive_ratio=separation.crop_positive_ratio if separation is not None else 0.0,
            person_panel_crop_max_confidence=separation.crop_max_confidence if separation is not None else 0.0,
        )


@dataclass
class _LiveSeparationSummary:
    sample_count: int = 0
    total_candidate_frames: int = 0
    source_candidate_frames: int = 0
    worker_overlap_frames: int = 0
    static_frames: int = 0
    max_visible_ratio: float = 0.0
    max_signal: float = 0.0
    crop_positive_frames: int = 0
    crop_negative_frames: int = 0
    crop_total_frames: int = 0
    crop_max_confidence: float = 0.0

    def update(self, frame_result: dict[str, Any], crop_summary: dict[str, Any] | None = None) -> None:
        self.sample_count += 1
        decision = str(frame_result.get("separation_decision") or "insufficient_visibility")
        zone = str(frame_result.get("zone") or "unknown")
        if decision == "separable_panel_candidate":
            self.total_candidate_frames += 1
            if zone != "output":
                self.source_candidate_frames += 1
        elif decision == "worker_body_overlap":
            self.worker_overlap_frames += 1
        elif decision == "static_or_background_edge":
            self.static_frames += 1
        self.max_visible_ratio = max(self.max_visible_ratio, float(frame_result.get("visible_nonperson_ratio") or 0.0))
        self.max_signal = max(
            self.max_signal,
            float(frame_result.get("estimated_visible_nonperson_region_signal") or 0.0),
            float(frame_result.get("mesh_signal_nonperson_score") or 0.0),
            float(frame_result.get("mesh_signal_border_score") or 0.0),
        )
        crop_summary = crop_summary or {}
        crop_recommendation = str(crop_summary.get("recommendation") or "")
        if int(crop_summary.get("prediction_count") or 0) > 0:
            self.crop_total_frames += 1
            if crop_recommendation == "carried_panel":
                self.crop_positive_frames += 1
            elif crop_recommendation == "worker_only":
                self.crop_negative_frames += 1
            self.crop_max_confidence = max(
                self.crop_max_confidence,
                float(crop_summary.get("carried_panel_max_confidence") or 0.0),
            )

    @property
    def recommendation(self) -> str | None:
        if self.sample_count <= 0:
            return None
        if self.source_candidate_frames >= 2:
            return "countable_panel_candidate"
        if self.total_candidate_frames == 0 and self.static_frames > 0 and self.worker_overlap_frames == 0:
            return "not_panel"
        if self.worker_overlap_frames == self.sample_count:
            return "not_panel"
        return "insufficient_visibility"

    @property
    def crop_positive_ratio(self) -> float:
        if self.crop_total_frames <= 0:
            return 0.0
        return self.crop_positive_frames / self.crop_total_frames

    @property
    def crop_recommendation(self) -> str | None:
        if self.crop_total_frames <= 0:
            return None
        if self.crop_positive_frames >= 1 and self.crop_positive_ratio >= 0.75 and self.crop_max_confidence >= 0.95:
            return "carried_panel"
        if self.crop_negative_frames >= 1 and self.crop_negative_frames >= self.crop_positive_frames:
            return "worker_only"
        return "insufficient_visibility"


class SimpleBoxTracker:
    def __init__(self, *, max_match_distance: float = 30.0, max_missing_frames: int = 1) -> None:
        self.max_match_distance = max_match_distance
        self.max_missing_frames = max_missing_frames
        self._next_id = 1
        self._tracks: dict[int, _SimpleTrack] = {}
        self.last_metadata_by_track_id: dict[int, dict[str, Any]] = {}

    def update(self, detections: list[dict[str, Any]]) -> list[TrackDetection]:
        assigned_detections: set[int] = set()
        output: list[TrackDetection] = []
        self.last_metadata_by_track_id = {}

        detection_boxes = [normalize_detection_box(detection["box"]) for detection in detections]
        detection_centers = [box_center(box) for box in detection_boxes]

        for track_id, track in list(self._tracks.items()):
            best_index = None
            best_distance = float("inf")
            for index, center in enumerate(detection_centers):
                if index in assigned_detections:
                    continue
                distance = _distance(track.center, center)
                if distance < best_distance:
                    best_distance = distance
                    best_index = index
            if best_index is not None and best_distance <= self.max_match_distance:
                box = detection_boxes[best_index]
                metadata = detector_metadata(detections[best_index])
                track.center = detection_centers[best_index]
                track.bbox = box
                track.metadata = metadata
                track.missing_frames = 0
                self.last_metadata_by_track_id[track_id] = metadata
                assigned_detections.add(best_index)
                output.append(
                    TrackDetection(
                        track_id=track_id,
                        bbox=box,
                        confidence=float(detections[best_index].get("confidence", 1.0)),
                    )
                )
            else:
                track.missing_frames += 1
                if track.missing_frames > self.max_missing_frames:
                    del self._tracks[track_id]

        for index, box in enumerate(detection_boxes):
            if index in assigned_detections:
                continue
            track_id = self._next_id
            self._next_id += 1
            center = detection_centers[index]
            metadata = detector_metadata(detections[index])
            self._tracks[track_id] = _SimpleTrack(track_id=track_id, center=center, bbox=box, metadata=metadata)
            self.last_metadata_by_track_id[track_id] = metadata
            output.append(
                TrackDetection(
                    track_id=track_id,
                    bbox=box,
                    confidence=float(detections[index].get("confidence", 1.0)),
                )
            )

        return sorted(output, key=lambda item: item.track_id)


class RuntimeEventCounter:
    def __init__(
        self,
        *,
        zones: CalibrationZones,
        gate: Gate | None,
        source_min_frames: int = 2,
        output_stable_frames: int = 2,
        tracker_match_distance: float = 30.0,
        tracker_max_missing_frames: int = 3,
        separation_analyzer: SeparationAnalyzer = analyze_frame_person_panel_separation,
        crop_classifier: CropClassifier | None = summarize_panel_box_crop,
        gate_config: GateConfig | None = None,
    ) -> None:
        self._zones = zones
        self._tracker_match_distance = tracker_match_distance
        self._tracker_max_missing_frames = max(1, tracker_max_missing_frames)
        self._gate_config = gate_config or GateConfig()
        self._separation_analyzer = separation_analyzer
        self._crop_classifier = crop_classifier
        self._count_config = CountConfig(
            zones=zones,
            gate=gate,
            source_min_frames=source_min_frames,
            output_stable_frames=output_stable_frames,
            source_overlap_threshold=0.25,
            output_overlap_threshold=0.25,
            stable_center_epsilon=3.0,
            disappear_in_output_frames=1,
            resident_match_center_distance=tracker_match_distance * 0.75,
        )
        self._reset_state()

    @property
    def total_count(self) -> int:
        return self._state_machine.total_count

    def reset(self) -> None:
        self._reset_state()

    def process_frame(
        self,
        *,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        person_boxes: list[Box] | None = None,
    ) -> RuntimeFrameResult:
        person_boxes = person_boxes or []
        enriched_detections = enrich_detections_with_person_overlap(detections, person_boxes) if person_boxes else detections
        tracked = self._tracker.update(enriched_detections)
        tracked_by_id = {item.track_id: item for item in tracked}

        for item in tracked:
            metadata = self._tracker.last_metadata_by_track_id.get(item.track_id)
            accumulator = self._gate_accumulators.setdefault(
                item.track_id,
                _TrackGateAccumulator(track_id=item.track_id, zones=self._zones),
            )
            accumulator.update(item, metadata, frame_index=self._frame_index)
            selected_person_box = _select_person_box(item.bbox, person_boxes)
            if selected_person_box is None:
                continue
            frame_result = self._separation_analyzer(
                image=frame,
                panel_box_xywh=item.bbox,
                person_box_xywh=selected_person_box,
                zone=accumulator.last_zone,
            )
            crop_summary = None
            if self._crop_classifier is not None and str(frame_result.get("separation_decision") or "") != "separable_panel_candidate":
                crop_summary = self._crop_classifier(
                    image=frame,
                    panel_box_xywh=item.bbox,
                    zone=accumulator.last_zone,
                )
            summary = self._separation_summaries.setdefault(item.track_id, _LiveSeparationSummary())
            summary.update(frame_result, crop_summary)

        gate_decisions: dict[int, GateDecision] = {}
        approved_track_ids: set[int] = set()
        approved_delivery_chains: list[tuple[str, int, int, Box]] = []
        for track_id, accumulator in self._gate_accumulators.items():
            separation = self._separation_summaries.get(track_id)
            predecessor_ids = self._select_gate_predecessor_chain(track_id, accumulator)
            merged_accumulator = accumulator
            merged_separation = separation
            if predecessor_ids:
                merged_accumulator = self._gate_accumulators[predecessor_ids[0]]
                for predecessor_id in predecessor_ids[1:] + [track_id]:
                    merged_accumulator = merge_gate_accumulators(
                        merged_accumulator,
                        self._gate_accumulators[predecessor_id],
                    )
                merged_separation = self._separation_summaries.get(predecessor_ids[0])
                for predecessor_id in predecessor_ids[1:] + [track_id]:
                    merged_separation = merge_separation_summaries(
                        merged_separation,
                        self._separation_summaries.get(predecessor_id),
                    )
            decision = evaluate_track(merged_accumulator.to_features(merged_separation), self._gate_config)
            gate_decisions[track_id] = decision
            if decision.decision == "allow_source_token":
                approved_track_ids.add(track_id)
                tracked_item = tracked_by_id.get(track_id)
                if tracked_item is not None:
                    source_track_id = predecessor_ids[0] if predecessor_ids else track_id
                    approved_delivery_chains.append(
                        (
                            f"proof-source-track:{source_track_id}",
                            source_track_id,
                            track_id,
                            tracked_item.bbox,
                        )
                    )

        events = self._state_machine.update(tracked, approved_track_ids=approved_track_ids)
        for chain_id, source_track_id, output_track_id, output_bbox in approved_delivery_chains:
            event = self._state_machine.commit_approved_delivery_chain(
                chain_id=chain_id,
                source_track_id=source_track_id,
                output_track_id=output_track_id,
                output_bbox=output_bbox,
            )
            if event is not None:
                events.append(event)
        self._frame_index += 1
        return RuntimeFrameResult(events=events, gate_decisions=gate_decisions, tracks=tracked)

    def _reset_state(self) -> None:
        self._tracker = SimpleBoxTracker(
            max_match_distance=self._tracker_match_distance,
            max_missing_frames=self._tracker_max_missing_frames,
        )
        self._gate_accumulators: dict[int, _TrackGateAccumulator] = {}
        self._separation_summaries: dict[int, _LiveSeparationSummary] = {}
        self._state_machine = CountStateMachine(self._count_config)
        self._frame_index = 0

    def _select_gate_predecessor(self, track_id: int, accumulator: _TrackGateAccumulator) -> int | None:
        if not accumulator.centers:
            return None
        output_center = accumulator.centers[0]
        max_link_distance = max(self._tracker_match_distance * 12.0, 500.0)
        max_gap_frames = max(self._tracker_max_missing_frames * 2 + 1, 3)
        candidates: list[tuple[int, float, int, int]] = []
        for candidate_id, candidate in self._gate_accumulators.items():
            if candidate_id == track_id or candidate.source_frames < self._count_config.source_min_frames:
                continue
            if candidate.output_frames > 0:
                continue
            if not candidate.centers:
                continue
            if candidate.last_seen_frame_index < 0 or accumulator.first_seen_frame_index < 0:
                continue
            gap_frames = accumulator.first_seen_frame_index - candidate.last_seen_frame_index
            if gap_frames <= 0 or gap_frames > max_gap_frames:
                continue
            distance = _distance(candidate.centers[-1], output_center)
            if distance > max_link_distance:
                continue
            candidates.append((gap_frames, distance, -candidate.source_frames, candidate_id))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][3]

    def _select_gate_predecessor_chain(self, track_id: int, accumulator: _TrackGateAccumulator) -> list[int]:
        if accumulator.output_frames <= 0 or accumulator.source_frames > 1:
            return []
        predecessor_ids: list[int] = []
        current_id = track_id
        current_accumulator = accumulator
        for _ in range(3):
            predecessor_id = self._select_gate_predecessor(current_id, current_accumulator)
            if predecessor_id is None:
                break
            predecessor_ids.append(predecessor_id)
            current_id = predecessor_id
            current_accumulator = self._gate_accumulators[predecessor_id]
        predecessor_ids.reverse()
        return predecessor_ids


def load_runtime_calibration(path: Path) -> tuple[CalibrationZones, Gate | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_polygons = payload.get("source_polygons") or []
    output_polygons = payload.get("output_polygons") or []
    ignore_polygons = payload.get("ignore_polygons") or []
    if not source_polygons or not output_polygons:
        raise ValueError("runtime calibration must include source_polygons and output_polygons")
    zones = CalibrationZones(
        source_polygons=_normalize_polygons(source_polygons),
        output_polygons=_normalize_polygons(output_polygons),
        ignore_polygons=_normalize_polygons(ignore_polygons),
    )
    gate_payload = payload.get("gate")
    gate = None
    if gate_payload:
        gate = Gate(
            start=tuple(gate_payload["start"]),  # type: ignore[arg-type]
            end=tuple(gate_payload["end"]),  # type: ignore[arg-type]
            source_side=int(gate_payload.get("source_side", 1)),
        )
    return zones, gate


def detector_metadata(detection: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in detection.items() if key not in {"box", "confidence"}}


def normalize_detection_box(box: Any) -> Box:
    x, y, width, height = [float(value) for value in box]
    if width <= 0 or height <= 0:
        raise ValueError("detection boxes must be xywh with positive width/height")
    return (x, y, width, height)


def box_overlap_fraction(box: Box, other: Box) -> float:
    x1, y1, width, height = box
    ox1, oy1, other_width, other_height = other
    x2 = x1 + width
    y2 = y1 + height
    ox2 = ox1 + other_width
    oy2 = oy1 + other_height
    ix1 = max(x1, ox1)
    iy1 = max(y1, oy1)
    ix2 = min(x2, ox2)
    iy2 = min(y2, oy2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    area = max(width * height, 1e-6)
    return max(0.0, min(1.0, ((ix2 - ix1) * (iy2 - iy1)) / area))


def enrich_detections_with_person_overlap(detections: list[dict[str, Any]], person_boxes: list[Box]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for detection in detections:
        item = dict(detection)
        box = normalize_detection_box(item["box"])
        overlap = max((box_overlap_fraction(box, person_box) for person_box in person_boxes), default=0.0)
        item["person_overlap_ratio"] = max(float(item.get("person_overlap_ratio", 0.0)), overlap)
        item["outside_person_ratio"] = min(float(item.get("outside_person_ratio", 1.0)), max(0.0, 1.0 - overlap))
        enriched.append(item)
    return enriched


def merge_gate_accumulators(
    predecessor: _TrackGateAccumulator,
    current: _TrackGateAccumulator,
) -> _TrackGateAccumulator:
    centers = list(predecessor.centers) + list(current.centers)
    first_center = centers[0] if centers else None
    max_displacement = max(predecessor.max_displacement, current.max_displacement)
    if first_center is not None:
        for center in centers:
            max_displacement = max(max_displacement, _distance(first_center, center))
    zones_seen = list(predecessor.zones_seen)
    for zone in current.zones_seen:
        if zone not in zones_seen:
            zones_seen.append(zone)
    merged = _TrackGateAccumulator(track_id=current.track_id, zones=current.zones)
    merged.first_zone = predecessor.first_zone
    merged.last_zone = current.last_zone
    merged.source_frames = predecessor.source_frames + current.source_frames
    merged.output_frames = predecessor.output_frames + current.output_frames
    merged.zones_seen = zones_seen
    merged.centers = centers
    merged.detections = predecessor.detections + current.detections
    merged.max_displacement = max_displacement
    merged.person_overlap_ratio = max(predecessor.person_overlap_ratio, current.person_overlap_ratio)
    merged.outside_person_ratio = min(predecessor.outside_person_ratio, current.outside_person_ratio)
    merged.static_stack_overlap_ratio = max(
        predecessor.static_stack_overlap_ratio,
        current.static_stack_overlap_ratio,
    )
    return merged


def merge_separation_summaries(
    predecessor: _LiveSeparationSummary | None,
    current: _LiveSeparationSummary | None,
) -> _LiveSeparationSummary | None:
    if predecessor is None:
        return current
    if current is None:
        return predecessor
    merged = _LiveSeparationSummary()
    merged.sample_count = predecessor.sample_count + current.sample_count
    merged.total_candidate_frames = predecessor.total_candidate_frames + current.total_candidate_frames
    merged.source_candidate_frames = predecessor.source_candidate_frames + current.source_candidate_frames
    merged.worker_overlap_frames = predecessor.worker_overlap_frames + current.worker_overlap_frames
    merged.static_frames = predecessor.static_frames + current.static_frames
    merged.max_visible_ratio = max(predecessor.max_visible_ratio, current.max_visible_ratio)
    merged.max_signal = max(predecessor.max_signal, current.max_signal)
    merged.crop_positive_frames = predecessor.crop_positive_frames + current.crop_positive_frames
    merged.crop_negative_frames = predecessor.crop_negative_frames + current.crop_negative_frames
    merged.crop_total_frames = predecessor.crop_total_frames + current.crop_total_frames
    merged.crop_max_confidence = max(predecessor.crop_max_confidence, current.crop_max_confidence)
    return merged


def _select_person_box(panel_box: Box, person_boxes: list[Box]) -> Optional[Box]:
    if not person_boxes:
        return None
    panel_center = box_center(panel_box)

    def key(box: Box) -> tuple[float, float]:
        overlap = box_overlap_fraction(panel_box, box)
        distance = _distance(panel_center, box_center(box))
        return (overlap, -distance)

    return max(person_boxes, key=key)


def _normalize_polygons(value: Any) -> list[list[tuple[float, float]]]:
    polygons: list[list[tuple[float, float]]] = []
    for polygon in value:
        points: list[tuple[float, float]] = []
        for point in polygon:
            points.append((float(point[0]), float(point[1])))
        if len(points) >= 3:
            polygons.append(points)
    return polygons


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return float((dx * dx + dy * dy) ** 0.5)
