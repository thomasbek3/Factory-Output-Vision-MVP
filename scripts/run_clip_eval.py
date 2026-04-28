#!/usr/bin/env python3
"""Run clip/frame-manifest evaluation through detector, tracker, count state machine, and ledger."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.calibration import Box, CalibrationZones, Gate, box_center, zone_membership
from app.services.count_state_machine import CountConfig, CountStateMachine, TrackDetection
from app.services.event_ledger import CountEventRecord, EventLedger, ResidentObject
from app.services.perception_gate import GateConfig, GateDecision, GateTrackFeatures, evaluate_track, summarize_gate_decisions

DEFAULT_OUT_DIR = Path("data/eval/clip-eval")
DetectorRunner = Callable[..., list[dict[str, Any]]]
PersonDetectorRunner = Callable[..., list[Box]]


@dataclass
class _SimpleTrack:
    track_id: int
    center: tuple[float, float]
    bbox: Box
    missing_frames: int = 0
    metadata: dict[str, Any] | None = None


@dataclass
class _TrackedFrame:
    frame_index: int
    row: dict[str, Any]
    tracks: list[TrackDetection]


@dataclass
class _TrackGateAccumulator:
    track_id: int
    zones: CalibrationZones
    first_zone: str = "outside"
    source_frames: int = 0
    output_frames: int = 0
    zones_seen: list[str] = field(default_factory=list)
    centers: list[tuple[float, float]] = field(default_factory=list)
    detections: int = 0
    max_displacement: float = 0.0
    person_overlap_ratio: float = 0.0
    outside_person_ratio: float = 1.0
    static_stack_overlap_ratio: float = 0.0

    def update(self, detection: TrackDetection, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or {}
        membership = zone_membership(detection.bbox, self.zones)
        zone = "outside"
        if membership.source_overlap >= 0.25:
            zone = "source"
            self.source_frames += 1
        elif membership.output_overlap >= 0.25:
            zone = "output"
            self.output_frames += 1
        if self.detections == 0:
            self.first_zone = zone
        if zone not in self.zones_seen:
            self.zones_seen.append(zone)
        center = box_center(detection.bbox)
        if self.centers:
            first = self.centers[0]
            self.max_displacement = max(self.max_displacement, _distance(first, center))
        self.centers.append(center)
        self.detections += 1
        self.person_overlap_ratio = max(self.person_overlap_ratio, float(metadata.get("person_overlap_ratio", 0.0)))
        self.outside_person_ratio = min(self.outside_person_ratio, float(metadata.get("outside_person_ratio", 1.0)))
        self.static_stack_overlap_ratio = max(
            self.static_stack_overlap_ratio,
            float(metadata.get("static_stack_overlap_ratio", metadata.get("static_overlap_ratio", 0.0))),
        )

    def to_features(self) -> GateTrackFeatures:
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
        )


class SimpleBoxTracker:
    def __init__(self, *, max_match_distance: float = 30.0, max_missing_frames: int = 1) -> None:
        self.max_match_distance = max_match_distance
        self.max_missing_frames = max_missing_frames
        self._next_id = 1
        self._tracks: dict[int, _SimpleTrack] = {}
        self.last_metadata_by_track_id: dict[int, dict[str, Any]] = {}

    def update(self, detections: list[dict[str, Any]]) -> list[TrackDetection]:
        assigned_detections: set[int] = set()
        assigned_tracks: set[int] = set()
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
                assigned_tracks.add(track_id)
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
            assigned_tracks.add(track_id)
            output.append(
                TrackDetection(
                    track_id=track_id,
                    bbox=box,
                    confidence=float(detections[index].get("confidence", 1.0)),
                )
            )

        return sorted(output, key=lambda item: item.track_id)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Factory Vision clip-level event evaluation.")
    parser.add_argument("--manifest", type=Path, required=True, help="Selected frame manifest JSON")
    parser.add_argument("--calibration", type=Path, required=True, help="Calibration zones JSON")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model", type=Path, default=None, help="YOLO .pt model path")
    parser.add_argument("--person-model", type=Path, default=None, help="Optional COCO person detector model for perception-gate overlap")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--force", action="store_true", help="Overwrite existing eval output directory")
    parser.add_argument("--source-min-frames", type=int, default=2)
    parser.add_argument("--output-stable-frames", type=int, default=2)
    parser.add_argument("--tracker-match-distance", type=float, default=30.0)
    parser.add_argument(
        "--enable-perception-gate",
        action="store_true",
        help="Evaluate full-track perception gate before source-token counting",
    )
    return parser.parse_args(argv)


def load_frame_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("frame manifest must be a list")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"manifest row {index} must be an object")
        rows.append(
            {
                "frame_path": str(row.get("frame_path", "")),
                "video_path": str(row.get("video_path", "")),
                "timestamp_seconds": float(row.get("timestamp_seconds", row.get("timestamp", index))),
                "width": int(row.get("width") or 0),
                "height": int(row.get("height") or 0),
            }
        )
    return rows


def load_calibration(calibration_path: Path) -> CalibrationZones:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    source_polygons = payload.get("source_polygons") or []
    output_polygons = payload.get("output_polygons") or []
    ignore_polygons = payload.get("ignore_polygons") or []
    if not source_polygons or not output_polygons:
        raise ValueError("calibration must include source_polygons and output_polygons")
    return CalibrationZones(
        source_polygons=_normalize_polygons(source_polygons),
        output_polygons=_normalize_polygons(output_polygons),
        ignore_polygons=_normalize_polygons(ignore_polygons),
    )


def load_gate(calibration_path: Path) -> Gate | None:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    gate_payload = payload.get("gate")
    if not gate_payload:
        return None
    return Gate(
        start=tuple(gate_payload["start"]),  # type: ignore[arg-type]
        end=tuple(gate_payload["end"]),  # type: ignore[arg-type]
        source_side=int(gate_payload.get("source_side", 1)),
    )


def run_clip_eval(
    *,
    manifest_path: Path,
    calibration_path: Path,
    out_dir: Path,
    model_path: Path | None,
    confidence: float,
    force: bool,
    detector_runner: DetectorRunner | None = None,
    person_detector_runner: PersonDetectorRunner | None = None,
    person_model_path: Path | None = None,
    source_min_frames: int = 2,
    output_stable_frames: int = 2,
    tracker_match_distance: float = 30.0,
    enable_perception_gate: bool = False,
) -> dict[str, Any]:
    if confidence < 0 or confidence > 1 or not math.isfinite(confidence):
        raise ValueError("confidence must be between 0 and 1")
    prepare_out_dir(out_dir, force=force)

    rows = load_frame_manifest(manifest_path)
    zones = load_calibration(calibration_path)
    gate = load_gate(calibration_path)
    detector = detector_runner or run_yolo_detector
    person_detector = person_detector_runner or (run_person_detector if person_model_path is not None else None)
    tracker = SimpleBoxTracker(max_match_distance=tracker_match_distance)
    tracked_frames: list[_TrackedFrame] = []
    gate_accumulators: dict[int, _TrackGateAccumulator] = {}

    for frame_index, row in enumerate(rows, start=1):
        detections = detector(
            frame=None,
            frame_index=frame_index,
            frame_row=row,
            model_path=model_path,
            confidence=confidence,
        )
        if person_detector is not None:
            person_boxes = person_detector(
                frame=None,
                frame_index=frame_index,
                frame_row=row,
                model_path=person_model_path,
                confidence=0.25,
            )
            detections = enrich_detections_with_person_overlap(detections, person_boxes)
        tracked = tracker.update(detections)
        tracked_frames.append(_TrackedFrame(frame_index=frame_index, row=row, tracks=tracked))
        if enable_perception_gate:
            for item in tracked:
                accumulator = gate_accumulators.setdefault(
                    item.track_id,
                    _TrackGateAccumulator(track_id=item.track_id, zones=zones),
                )
                accumulator.update(item, tracker.last_metadata_by_track_id.get(item.track_id))

    gate_decisions: list[GateDecision] = []
    gate_decision_by_track: dict[int, GateDecision] = {}
    allowed_track_ids: set[int] | None = None
    if enable_perception_gate:
        gate_decisions = [evaluate_track(item.to_features(), GateConfig()) for item in gate_accumulators.values()]
        gate_decision_by_track = {item.track_id: item for item in gate_decisions}
        allowed_track_ids = {item.track_id for item in gate_decisions if item.decision == "allow_source_token"}

    state_machine = CountStateMachine(
        CountConfig(
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
    )
    ledger = EventLedger(out_dir)
    tracks_path = out_dir / "tracks.jsonl"
    review_dir = out_dir / "review_cards"
    review_dir.mkdir(parents=True, exist_ok=True)

    count_events = 0
    uncertain_events = 0
    for tracked_frame in tracked_frames:
        frame_index = tracked_frame.frame_index
        row = tracked_frame.row
        tracked = tracked_frame.tracks
        state_machine_tracks = tracked
        if allowed_track_ids is not None:
            state_machine_tracks = [item for item in tracked if item.track_id in allowed_track_ids]
        events = state_machine.update(state_machine_tracks)
        _append_jsonl(
            tracks_path,
            {
                "frame_index": frame_index,
                "timestamp_seconds": row["timestamp_seconds"],
                "frame_path": row["frame_path"],
                "tracks": [
                    {
                        "track_id": item.track_id,
                        "bbox": list(item.bbox),
                        "confidence": item.confidence,
                        "state": state_machine.track_state(item.track_id),
                        "state_path": state_machine.track_state_path(item.track_id),
                        "uncertain_reasons": state_machine.track_uncertain_reasons(item.track_id),
                        "perception_gate": gate_decision_payload(gate_decision_by_track.get(item.track_id)),
                    }
                    for item in tracked
                ],
            },
        )
        for event in events:
            count_events += 1
            event_id = f"count-{count_events:06d}"
            resident_id = f"resident-{count_events:06d}"
            token_id = f"source-token-track-{event.track_id}"
            state_path = state_machine.track_state_path(event.track_id)
            ledger.record_count(
                CountEventRecord(
                    event_id=event_id,
                    frame_index=frame_index,
                    track_id=event.track_id,
                    source_token_id=token_id,
                    resident_id=resident_id,
                    reason=event.reason,
                    bbox=event.bbox,
                    state_path=state_path,
                    evidence_score=1.0,
                ),
                resident=ResidentObject(
                    resident_id=resident_id,
                    track_id=event.track_id,
                    created_frame=frame_index,
                    bbox=event.bbox,
                    source_token_id=token_id,
                ),
            )
            write_review_card(
                review_dir / f"{event_id}.json",
                {
                    "event_id": event_id,
                    "frame_index": frame_index,
                    "timestamp_seconds": row["timestamp_seconds"],
                    "frame_path": row["frame_path"],
                    "track_id": event.track_id,
                    "reason": event.reason,
                    "bbox": list(event.bbox),
                    "state_path": state_path,
                },
            )

        for item in tracked:
            reasons = state_machine.track_uncertain_reasons(item.track_id)
            if reasons:
                uncertain_events += 1

    summary = {
        "schema_version": "factory-clip-eval-v1",
        "manifest_path": manifest_path.as_posix(),
        "calibration_path": calibration_path.as_posix(),
        "model_path": model_path.as_posix() if model_path is not None else None,
        "person_model_path": person_model_path.as_posix() if person_model_path is not None else None,
        "frames_processed": len(rows),
        "total_count": state_machine.total_count,
        "count_events": count_events,
        "uncertain_track_observations": uncertain_events,
        "perception_gate_enabled": enable_perception_gate,
        "perception_gate_summary": summarize_gate_decisions(gate_decisions) if enable_perception_gate else None,
        "outputs": {
            "events_jsonl": (out_dir / "events.jsonl").as_posix(),
            "residents_jsonl": (out_dir / "residents.jsonl").as_posix(),
            "tracks_jsonl": tracks_path.as_posix(),
            "review_cards_dir": review_dir.as_posix(),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def detector_metadata(detection: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in detection.items() if key not in {"box", "confidence"}}


def gate_decision_payload(decision: GateDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "track_id": decision.track_id,
        "decision": decision.decision,
        "reason": decision.reason,
        "flags": list(decision.flags),
        "evidence": decision.evidence,
    }


def prepare_out_dir(out_dir: Path, *, force: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{out_dir} already exists and is not empty; pass --force")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def run_yolo_detector(
    *,
    frame: Any,
    frame_index: int,
    frame_row: dict[str, Any],
    model_path: Path | None,
    confidence: float,
) -> list[dict[str, Any]]:
    if model_path is None:
        raise ValueError("--model is required unless a detector_runner is injected")
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    frame_path = frame_row.get("frame_path")
    results = model.predict(str(frame_path), conf=confidence, verbose=False, device="cpu")
    detections: list[dict[str, Any]] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        xyxy_values = _to_list(getattr(boxes, "xyxy", []))
        confidence_values = _to_list(getattr(boxes, "conf", []))
        for xyxy, score in zip(xyxy_values, confidence_values):
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append({"box": (x1, y1, x2 - x1, y2 - y1), "confidence": float(score)})
    return detections


def run_person_detector(
    *,
    frame: Any,
    frame_index: int,
    frame_row: dict[str, Any],
    model_path: Path | None,
    confidence: float,
) -> list[Box]:
    if model_path is None:
        raise ValueError("--person-model is required for person detection")
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    frame_path = frame_row.get("frame_path")
    results = model.predict(str(frame_path), conf=confidence, classes=[0], verbose=False, device="cpu")
    person_boxes: list[Box] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for xyxy in _to_list(getattr(boxes, "xyxy", [])):
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            if x2 <= x1 or y2 <= y1:
                continue
            person_boxes.append((x1, y1, x2 - x1, y2 - y1))
    return person_boxes


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


def normalize_detection_box(box: Any) -> Box:
    x, y, width, height = [float(value) for value in box]
    if width <= 0 or height <= 0:
        raise ValueError("detection boxes must be xywh with positive width/height")
    return (x, y, width, height)


def write_review_card(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _normalize_polygons(value: Any) -> list[list[tuple[float, float]]]:
    polygons: list[list[tuple[float, float]]] = []
    for polygon in value:
        points: list[tuple[float, float]] = []
        for point in polygon:
            if len(point) != 2:
                raise ValueError("polygon points must be [x, y]")
            points.append((float(point[0]), float(point[1])))
        if len(points) < 3:
            raise ValueError("polygons must have at least 3 points")
        polygons.append(points)
    return polygons


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = run_clip_eval(
            manifest_path=args.manifest,
            calibration_path=args.calibration,
            out_dir=args.out_dir,
            model_path=args.model,
            person_model_path=args.person_model,
            confidence=args.confidence,
            force=args.force,
            source_min_frames=args.source_min_frames,
            output_stable_frames=args.output_stable_frames,
            tracker_match_distance=args.tracker_match_distance,
            enable_perception_gate=args.enable_perception_gate,
        )
    except (FileExistsError, FileNotFoundError, ValueError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
