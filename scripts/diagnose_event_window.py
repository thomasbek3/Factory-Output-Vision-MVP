#!/usr/bin/env python3
"""Generate forensic diagnostics for a factory event window.

This is intentionally not the counter. It is the pixel-level debugger that answers:
- did the detector see an active panel or a static stack edge?
- did the region move internally?
- did the track have source evidence before output evidence?
- can we produce a visual receipt worth sending to an AI auditor?
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.calibration import Box, CalibrationZones, box_center, point_in_polygon
from app.services.perception_gate import GateConfig, GateDecision, GateTrackFeatures, evaluate_track, summarize_gate_decisions
from app.services.person_panel_gate_promotion import (
    load_person_panel_separation,
    person_panel_separation_features,
    person_panel_separation_path,
    promote_worker_overlap_gate_row,
    receipt_crop_classifier_features,
)
from scripts.run_clip_eval import SimpleBoxTracker, normalize_detection_box

DEFAULT_OUT_DIR = Path("data/diagnostics/event-windows")
FrameExtractor = Callable[..., list[Path]]
Analyzer = Callable[..., "AnalysisArtifacts"]
MediaMaker = Callable[..., None]
ReceiptCardMaker = Callable[..., Optional[Path]]


@dataclass(frozen=True)
class TrackEvidence:
    track_id: int
    first_timestamp: float
    last_timestamp: float
    first_zone: str
    zones_seen: list[str]
    source_frames: int
    output_frames: int
    max_displacement: float
    mean_internal_motion: float
    max_internal_motion: float
    detections: int
    static_location_ratio: float = 0.0
    flow_coherence: float = 0.0
    static_stack_overlap_ratio: float = 0.0
    person_overlap_ratio: float = 0.0
    outside_person_ratio: float = 1.0
    observations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class TrackDiagnosis:
    track_id: int
    decision: str
    reason: str
    flags: list[str]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class AnalysisArtifacts:
    track_evidence: list[TrackEvidence]
    overlay_frames: list[Path]
    frame_count: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose an event window with dense overlays, motion, and track evidence.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--person-model", type=Path, default=None, help="Optional COCO person detector model, e.g. yolo11n.pt")
    parser.add_argument("--confidence", type=float, default=0.20)
    parser.add_argument("--tracker-match-distance", type=float, default=220.0)
    parser.add_argument("--min-displacement", type=float, default=30.0)
    parser.add_argument("--min-internal-motion", type=float, default=0.04)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def prepare_output_dir(out_dir: Path, *, force: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{out_dir} already exists and is not empty; pass --force")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frames").mkdir(parents=True, exist_ok=True)
    (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (out_dir / "track_receipts").mkdir(parents=True, exist_ok=True)


def load_calibration(calibration_path: Path) -> CalibrationZones:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    source_polygons = _normalize_polygons(payload.get("source_polygons") or [])
    output_polygons = _normalize_polygons(payload.get("output_polygons") or [])
    ignore_polygons = _normalize_polygons(payload.get("ignore_polygons") or [])
    if not source_polygons or not output_polygons:
        raise ValueError("calibration must include source_polygons and output_polygons")
    return CalibrationZones(source_polygons=source_polygons, output_polygons=output_polygons, ignore_polygons=ignore_polygons)


def classify_track_evidence(
    track: TrackEvidence,
    *,
    min_displacement: float,
    min_internal_motion: float,
) -> TrackDiagnosis:
    flags: list[str] = []
    saw_source = track.source_frames > 0 or "source" in track.zones_seen
    saw_output = track.output_frames > 0 or "output" in track.zones_seen
    low_motion = track.max_internal_motion < min_internal_motion
    low_displacement = track.max_displacement < min_displacement

    if saw_output and not saw_source:
        flags.append("output_only_no_source_token")
    if low_motion:
        flags.append("low_internal_motion")
    if low_displacement:
        flags.append("low_track_displacement")
    if track.first_zone == "output":
        flags.append("started_in_output")

    if saw_source and saw_output and not low_displacement and not low_motion:
        decision = "candidate"
        reason = "source_to_output_motion"
    elif saw_output and not saw_source and low_motion:
        decision = "reject"
        reason = "static_stack_edge"
    elif saw_output and not saw_source:
        decision = "reject"
        reason = "output_only_no_source_token"
    elif saw_source and not saw_output:
        decision = "uncertain"
        reason = "source_without_output_settle"
    elif low_motion and low_displacement:
        decision = "reject"
        reason = "static_or_background_detection"
    else:
        decision = "uncertain"
        reason = "insufficient_source_to_output_evidence"

    return TrackDiagnosis(
        track_id=track.track_id,
        decision=decision,
        reason=reason,
        flags=flags,
        evidence=asdict(track),
    )


def diagnose_event_window(
    *,
    video_path: Path,
    calibration_path: Path,
    out_dir: Path,
    start_timestamp: float,
    end_timestamp: float,
    fps: float,
    model_path: Path | None,
    confidence: float,
    force: bool,
    person_model_path: Path | None = None,
    tracker_match_distance: float = 220.0,
    min_displacement: float = 30.0,
    min_internal_motion: float = 0.04,
    frame_extractor: FrameExtractor | None = None,
    analyzer: Analyzer | None = None,
    media_maker: MediaMaker | None = None,
    receipt_card_maker: ReceiptCardMaker | None = None,
) -> dict[str, Any]:
    if end_timestamp <= start_timestamp:
        raise ValueError("end timestamp must be after start timestamp")
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("fps must be positive")
    if confidence < 0 or confidence > 1 or not math.isfinite(confidence):
        raise ValueError("confidence must be between 0 and 1")

    prepare_output_dir(out_dir, force=force)
    zones = load_calibration(calibration_path)
    frames_dir = out_dir / "frames"
    overlay_dir = out_dir / "overlays"
    extract = frame_extractor or extract_dense_frames
    analyze = analyzer or analyze_frames
    make_media = media_maker or make_overlay_media
    make_receipt_card = receipt_card_maker or make_track_receipt_card

    frame_paths = extract(
        video_path=video_path,
        frames_dir=frames_dir,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        fps=fps,
    )
    artifacts = analyze(
        frame_paths=frame_paths,
        zones=zones,
        overlay_dir=overlay_dir,
        start_timestamp=start_timestamp,
        fps=fps,
        model_path=model_path,
        person_model_path=person_model_path,
        confidence=confidence,
        tracker_match_distance=tracker_match_distance,
    )

    diagnoses = [
        classify_track_evidence(
            track,
            min_displacement=min_displacement,
            min_internal_motion=min_internal_motion,
        )
        for track in artifacts.track_evidence
    ]
    gate_config = GateConfig(min_displacement=min_displacement, min_internal_motion=min_internal_motion)
    gate_decisions = [evaluate_track(gate_features_from_track(track), gate_config) for track in artifacts.track_evidence]

    sheet_path = out_dir / "overlay_sheet.jpg"
    overlay_video_path = out_dir / "overlay_video.mp4"
    make_media(overlay_frames=artifacts.overlay_frames, sheet_path=sheet_path, video_path=overlay_video_path, fps=fps)
    receipt_paths = write_track_receipts(
        out_dir=out_dir,
        tracks=artifacts.track_evidence,
        diagnoses=diagnoses,
        gate_decisions=gate_decisions,
        overlay_sheet_path=sheet_path,
        overlay_video_path=overlay_video_path,
        overlay_frames=artifacts.overlay_frames,
        start_timestamp=start_timestamp,
        fps=fps,
        receipt_card_maker=make_receipt_card,
    )
    hard_negative_manifest_path = write_hard_negative_manifest(
        out_dir=out_dir,
        tracks=artifacts.track_evidence,
        diagnoses=diagnoses,
        gate_decisions=gate_decisions,
        receipt_paths=receipt_paths,
    )

    result = {
        "schema_version": "factory-event-diagnostic-v1",
        "video_path": _rel(video_path),
        "calibration_path": _rel(calibration_path),
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "fps": fps,
        "model_path": _rel(model_path) if model_path else None,
        "person_model_path": _rel(person_model_path) if person_model_path else None,
        "confidence": confidence,
        "frame_count": artifacts.frame_count,
        "overlay_sheet_path": _rel(sheet_path),
        "overlay_video_path": _rel(overlay_video_path),
        "track_receipts": [_rel(path) for path in receipt_paths],
        "track_receipt_cards": [
            _rel(path.with_name(f"{path.stem}-sheet.jpg"))
            for path in receipt_paths
            if path.with_name(f"{path.stem}-sheet.jpg").exists()
        ],
        "hard_negative_manifest_path": _rel(hard_negative_manifest_path) if hard_negative_manifest_path is not None else None,
        "diagnosis": [asdict(item) for item in diagnoses],
        "summary": summarize_diagnoses(diagnoses),
        "perception_gate": [asdict(item) for item in gate_decisions],
        "perception_gate_summary": summarize_gate_decisions(gate_decisions),
    }
    (out_dir / "diagnostic.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def gate_features_from_track(track: TrackEvidence) -> GateTrackFeatures:
    return GateTrackFeatures(
        track_id=track.track_id,
        source_frames=track.source_frames,
        output_frames=track.output_frames,
        zones_seen=track.zones_seen,
        first_zone=track.first_zone,
        max_displacement=track.max_displacement,
        mean_internal_motion=track.mean_internal_motion,
        max_internal_motion=track.max_internal_motion,
        detections=track.detections,
        person_overlap_ratio=track.person_overlap_ratio,
        outside_person_ratio=track.outside_person_ratio,
        static_stack_overlap_ratio=track.static_stack_overlap_ratio,
        static_location_ratio=track.static_location_ratio,
        flow_coherence=track.flow_coherence,
    )


def gate_decision_from_row(row: dict[str, Any]) -> GateDecision:
    return GateDecision(
        track_id=int(row.get("track_id") or 0),
        decision=str(row.get("decision") or "unknown"),
        reason=str(row.get("reason") or "unknown"),
        flags=[str(flag) for flag in (row.get("flags") or [])],
        evidence=row.get("evidence") or {},
    )


def _value_or_default(mapping: dict[str, Any], key: str, default: Any) -> Any:
    value = mapping.get(key)
    return default if value is None else value


def track_evidence_from_payload(payload: dict[str, Any]) -> TrackEvidence:
    timestamps = payload.get("timestamps") or {}
    evidence = payload.get("evidence") or {}
    return TrackEvidence(
        track_id=int(evidence.get("track_id") or payload.get("track_id") or 0),
        first_timestamp=float(evidence.get("first_timestamp") or timestamps.get("first") or 0.0),
        last_timestamp=float(evidence.get("last_timestamp") or timestamps.get("last") or 0.0),
        first_zone=str(evidence.get("first_zone") or "unknown"),
        zones_seen=[str(zone) for zone in (evidence.get("zones_seen") or [])],
        source_frames=int(evidence.get("source_frames") or 0),
        output_frames=int(evidence.get("output_frames") or 0),
        max_displacement=float(evidence.get("max_displacement") or 0.0),
        mean_internal_motion=float(evidence.get("mean_internal_motion") or 0.0),
        max_internal_motion=float(evidence.get("max_internal_motion") or 0.0),
        detections=int(evidence.get("detections") or 0),
        static_location_ratio=float(evidence.get("static_location_ratio") or 0.0),
        flow_coherence=float(evidence.get("flow_coherence") or 0.0),
        static_stack_overlap_ratio=float(evidence.get("static_stack_overlap_ratio") or 0.0),
        person_overlap_ratio=float(evidence.get("person_overlap_ratio") or 0.0),
        outside_person_ratio=float(_value_or_default(evidence, "outside_person_ratio", 1.0)),
        observations=[item for item in (evidence.get("observations") or []) if isinstance(item, dict)],
    )


def track_observation_center(observation: dict[str, Any]) -> tuple[float, float] | None:
    box = observation.get("box_xywh")
    if not isinstance(box, list) or len(box) != 4:
        return None
    try:
        return box_center(tuple(float(value) for value in box))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def track_first_center(track: TrackEvidence) -> tuple[float, float] | None:
    for observation in track.observations:
        center = track_observation_center(observation)
        if center is not None:
            return center
    return None


def track_last_center(track: TrackEvidence) -> tuple[float, float] | None:
    for observation in reversed(track.observations):
        center = track_observation_center(observation)
        if center is not None:
            return center
    return None


def merge_zones_seen(predecessor: TrackEvidence, current: TrackEvidence) -> list[str]:
    zones_seen = list(predecessor.zones_seen)
    for zone in current.zones_seen:
        if zone not in zones_seen:
            zones_seen.append(zone)
    return zones_seen


def load_receipt_person_panel_features(receipt_path: Path) -> dict[str, Any]:
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    separation_payload = load_person_panel_separation(person_panel_separation_path(str(receipt_path)))
    features = person_panel_separation_features(separation_payload)
    features.update(receipt_crop_classifier_features(receipt_payload))
    summary = separation_payload.get("summary") or {}
    selected_frames = [item for item in (separation_payload.get("selected_frames") or []) if isinstance(item, dict)]
    frame_count = int(summary.get("frame_count") or len(selected_frames))
    worker_overlap_frames = int(summary.get("worker_body_overlap_frames") or 0)
    if worker_overlap_frames <= 0:
        worker_overlap_frames = sum(1 for item in selected_frames if item.get("separation_decision") == "worker_body_overlap")
    static_frames = int(summary.get("static_or_background_edge_frames") or 0)
    if static_frames <= 0:
        static_frames = sum(1 for item in selected_frames if item.get("separation_decision") == "static_or_background_edge")
    features.update(
        {
            "person_panel_frame_count": frame_count,
            "person_panel_worker_overlap_frames": worker_overlap_frames,
            "person_panel_static_frames": static_frames,
        }
    )
    return features


def merged_person_panel_features(receipt_paths: list[Path]) -> dict[str, Any]:
    merged = {
        "person_panel_total_candidate_frames": 0,
        "person_panel_source_candidate_frames": 0,
        "person_panel_max_visible_nonperson_ratio": 0.0,
        "person_panel_max_signal": 0.0,
        "person_panel_frame_count": 0,
        "person_panel_worker_overlap_frames": 0,
        "person_panel_static_frames": 0,
        "person_panel_crop_positive_crops": 0,
        "person_panel_crop_negative_crops": 0,
        "person_panel_crop_total_crops": 0,
        "person_panel_crop_positive_ratio": 0.0,
        "person_panel_crop_max_confidence": 0.0,
    }
    for receipt_path in receipt_paths:
        features = load_receipt_person_panel_features(receipt_path)
        merged["person_panel_total_candidate_frames"] += int(features.get("person_panel_total_candidate_frames") or 0)
        merged["person_panel_source_candidate_frames"] += int(features.get("person_panel_source_candidate_frames") or 0)
        merged["person_panel_max_visible_nonperson_ratio"] = max(
            float(merged["person_panel_max_visible_nonperson_ratio"]),
            float(features.get("person_panel_max_visible_nonperson_ratio") or 0.0),
        )
        merged["person_panel_max_signal"] = max(
            float(merged["person_panel_max_signal"]),
            float(features.get("person_panel_max_signal") or 0.0),
        )
        merged["person_panel_frame_count"] += int(features.get("person_panel_frame_count") or 0)
        merged["person_panel_worker_overlap_frames"] += int(features.get("person_panel_worker_overlap_frames") or 0)
        merged["person_panel_static_frames"] += int(features.get("person_panel_static_frames") or 0)
        merged["person_panel_crop_positive_crops"] += int(features.get("person_panel_crop_positive_crops") or 0)
        merged["person_panel_crop_negative_crops"] += int(features.get("person_panel_crop_negative_crops") or 0)
        merged["person_panel_crop_total_crops"] += int(features.get("person_panel_crop_total_crops") or 0)
        merged["person_panel_crop_positive_ratio"] = max(
            float(merged["person_panel_crop_positive_ratio"]),
            float(features.get("person_panel_crop_positive_ratio") or 0.0),
        )
        merged["person_panel_crop_max_confidence"] = max(
            float(merged["person_panel_crop_max_confidence"]),
            float(features.get("person_panel_crop_max_confidence") or 0.0),
        )

    frame_count = int(merged["person_panel_frame_count"])
    total_candidate_frames = int(merged["person_panel_total_candidate_frames"])
    source_candidate_frames = int(merged["person_panel_source_candidate_frames"])
    worker_overlap_frames = int(merged["person_panel_worker_overlap_frames"])
    static_frames = int(merged["person_panel_static_frames"])
    if frame_count <= 0:
        recommendation = None
    elif source_candidate_frames >= 2:
        recommendation = "countable_panel_candidate"
    elif total_candidate_frames == 0 and static_frames > 0 and worker_overlap_frames == 0:
        recommendation = "not_panel"
    elif worker_overlap_frames == frame_count:
        recommendation = "not_panel"
    else:
        recommendation = "insufficient_visibility"
    merged["person_panel_recommendation"] = recommendation
    crop_total = int(merged["person_panel_crop_total_crops"])
    crop_positive = int(merged["person_panel_crop_positive_crops"])
    crop_negative = int(merged["person_panel_crop_negative_crops"])
    if crop_total <= 0:
        crop_recommendation = ""
    elif crop_positive >= 1 and float(merged["person_panel_crop_positive_ratio"]) >= 0.75 and float(merged["person_panel_crop_max_confidence"]) >= 0.95:
        crop_recommendation = "carried_panel"
    elif crop_negative >= 1 and crop_negative >= crop_positive:
        crop_recommendation = "worker_only"
    else:
        crop_recommendation = "insufficient_visibility"
    merged["person_panel_crop_recommendation"] = crop_recommendation
    return merged


def merged_gate_features_from_tracks(
    tracks: list[TrackEvidence],
    *,
    receipt_paths: list[Path],
) -> GateTrackFeatures:
    centers = [
        center
        for track in tracks
        for center in (track_observation_center(item) for item in track.observations)
        if center is not None
    ]
    max_displacement = max((track.max_displacement for track in tracks), default=0.0)
    if centers:
        first_center = centers[0]
        max_displacement = max(max_displacement, max(_distance(first_center, center) for center in centers))
        static_location_ratio = round(calculate_static_location_ratio(centers), 6)
        flow_coherence = round(calculate_flow_coherence(centers), 6)
    else:
        total_detections = max(sum(track.detections for track in tracks), 1)
        static_location_ratio = round(
            sum(track.static_location_ratio * track.detections for track in tracks) / total_detections,
            6,
        )
        flow_coherence = round(max((track.flow_coherence for track in tracks), default=0.0), 6)

    total_detections = sum(track.detections for track in tracks)
    mean_internal_motion = 0.0
    if total_detections > 0:
        mean_internal_motion = round(
            sum(track.mean_internal_motion * track.detections for track in tracks) / total_detections,
            6,
        )

    separation = merged_person_panel_features(receipt_paths)
    first_track = tracks[0]
    current_track = tracks[-1]
    zones_seen = list(first_track.zones_seen)
    for track in tracks[1:]:
        for zone in track.zones_seen:
            if zone not in zones_seen:
                zones_seen.append(zone)
    return GateTrackFeatures(
        track_id=current_track.track_id,
        source_frames=sum(track.source_frames for track in tracks),
        output_frames=sum(track.output_frames for track in tracks),
        zones_seen=zones_seen,
        first_zone=first_track.first_zone,
        max_displacement=round(max_displacement, 6),
        mean_internal_motion=mean_internal_motion,
        max_internal_motion=max((track.max_internal_motion for track in tracks), default=0.0),
        detections=total_detections,
        person_overlap_ratio=max((track.person_overlap_ratio for track in tracks), default=0.0),
        outside_person_ratio=min((track.outside_person_ratio for track in tracks), default=1.0),
        static_stack_overlap_ratio=max((track.static_stack_overlap_ratio for track in tracks), default=0.0),
        static_location_ratio=static_location_ratio,
        flow_coherence=flow_coherence,
        person_panel_recommendation=str(separation.get("person_panel_recommendation") or ""),
        person_panel_total_candidate_frames=int(separation.get("person_panel_total_candidate_frames") or 0),
        person_panel_source_candidate_frames=int(separation.get("person_panel_source_candidate_frames") or 0),
        person_panel_max_visible_nonperson_ratio=float(separation.get("person_panel_max_visible_nonperson_ratio") or 0.0),
        person_panel_max_signal=float(separation.get("person_panel_max_signal") or 0.0),
        person_panel_crop_recommendation=str(separation.get("person_panel_crop_recommendation") or ""),
        person_panel_crop_positive_crops=int(separation.get("person_panel_crop_positive_crops") or 0),
        person_panel_crop_negative_crops=int(separation.get("person_panel_crop_negative_crops") or 0),
        person_panel_crop_total_crops=int(separation.get("person_panel_crop_total_crops") or 0),
        person_panel_crop_positive_ratio=float(separation.get("person_panel_crop_positive_ratio") or 0.0),
        person_panel_crop_max_confidence=float(separation.get("person_panel_crop_max_confidence") or 0.0),
    )


def select_gate_predecessor_index(
    tracks: list[TrackEvidence],
    *,
    current_index: int,
    fps: float,
) -> int | None:
    current = tracks[current_index]
    current_center = track_first_center(current)
    if current_center is None:
        return None
    max_gap_seconds = max(2.0, 4.0 / fps) if fps > 0 and math.isfinite(fps) else 2.0
    max_link_distance = 350.0
    candidates: list[tuple[float, float, int, int]] = []
    for index, predecessor in enumerate(tracks):
        if index == current_index or predecessor.source_frames < 2 or predecessor.output_frames > 0:
            continue
        if predecessor.last_timestamp > current.first_timestamp:
            continue
        gap = current.first_timestamp - predecessor.last_timestamp
        if gap > max_gap_seconds:
            continue
        predecessor_center = track_last_center(predecessor)
        if predecessor_center is None:
            continue
        distance = _distance(predecessor_center, current_center)
        if distance > max_link_distance:
            continue
        candidates.append((gap, distance, -predecessor.source_frames, index))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][3]


def select_gate_predecessor_chain_indices(
    tracks: list[TrackEvidence],
    *,
    current_index: int,
    fps: float,
    max_chain_length: int = 3,
) -> list[int]:
    current = tracks[current_index]
    if current.output_frames <= 0 or current.source_frames > 1:
        return []
    chain_indices: list[int] = []
    cursor = current_index
    for _ in range(max_chain_length):
        predecessor_index = select_gate_predecessor_index(tracks, current_index=cursor, fps=fps)
        if predecessor_index is None:
            break
        chain_indices.append(predecessor_index)
        cursor = predecessor_index
    return list(reversed(chain_indices))


def evaluate_receipt_gate_decisions(
    *,
    tracks: list[TrackEvidence],
    receipt_paths: list[Path],
    gate_config: GateConfig,
    fps: float,
    existing_gate_rows: dict[int, dict[str, Any]] | None = None,
) -> list[GateDecision]:
    gate_decisions: list[GateDecision] = []
    existing_gate_rows = existing_gate_rows or {}
    for index, (track, receipt_path) in enumerate(zip(tracks, receipt_paths)):
        base_row = existing_gate_rows.get(track.track_id)
        if base_row is None:
            base_row = asdict(evaluate_track(gate_features_from_track(track), gate_config))

        predecessor_chain = select_gate_predecessor_chain_indices(tracks, current_index=index, fps=fps)
        if predecessor_chain:
            chain_tracks = [tracks[item] for item in predecessor_chain] + [track]
            chain_receipts = [receipt_paths[item] for item in predecessor_chain] + [receipt_path]
            merged_features = merged_gate_features_from_tracks(
                chain_tracks,
                receipt_paths=chain_receipts,
            )
            merged_decision = evaluate_track(merged_features, gate_config)
            if merged_decision.decision == "allow_source_token":
                merged_evidence = dict(merged_decision.evidence)
                predecessor_track_ids = [tracks[item].track_id for item in predecessor_chain]
                merged_evidence["merged_predecessor_track_id"] = predecessor_track_ids[-1]
                merged_evidence["merged_predecessor_track_ids"] = predecessor_track_ids
                merged_evidence["merged_predecessor_receipt_paths"] = [_rel(receipt_paths[item]) for item in predecessor_chain]
                gate_decisions.append(
                    GateDecision(
                        track_id=merged_decision.track_id,
                        decision=merged_decision.decision,
                        reason=merged_decision.reason,
                        flags=merged_decision.flags,
                        evidence=merged_evidence,
                    )
                )
                continue

        promoted_row = promote_worker_overlap_gate_row(base_row, str(receipt_path))
        gate_decisions.append(gate_decision_from_row(promoted_row))
    return gate_decisions


def diagnosis_from_payload(payload: dict[str, Any], *, fallback_track: TrackEvidence) -> TrackDiagnosis:
    diagnosis = payload.get("diagnosis") or {}
    if diagnosis:
        return TrackDiagnosis(
            track_id=int(diagnosis.get("track_id") or fallback_track.track_id),
            decision=str(diagnosis.get("decision") or "unknown"),
            reason=str(diagnosis.get("reason") or "unknown"),
            flags=[str(flag) for flag in (diagnosis.get("flags") or [])],
            evidence=diagnosis.get("evidence") or {},
        )
    defaults = GateConfig()
    return classify_track_evidence(
        fallback_track,
        min_displacement=defaults.min_displacement,
        min_internal_motion=defaults.min_internal_motion,
    )


def write_track_receipts(
    *,
    out_dir: Path,
    tracks: list[TrackEvidence],
    diagnoses: list[TrackDiagnosis],
    gate_decisions: list[Any],
    overlay_sheet_path: Path,
    overlay_video_path: Path,
    overlay_frames: list[Path] | None = None,
    start_timestamp: float = 0.0,
    fps: float = 1.0,
    receipt_card_maker: ReceiptCardMaker | None = None,
    existing_receipt_payloads: dict[int, dict[str, Any]] | None = None,
) -> list[Path]:
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    diagnosis_by_track = {item.track_id: item for item in diagnoses}
    gate_by_track = {item.track_id: item for item in gate_decisions}
    paths: list[Path] = []
    for track in sorted(tracks, key=lambda item: item.track_id):
        diagnosis = diagnosis_by_track.get(track.track_id)
        gate = gate_by_track.get(track.track_id)
        path = receipts_dir / f"track-{track.track_id:06d}.json"
        card_path = receipts_dir / f"track-{track.track_id:06d}-sheet.jpg"
        if receipt_card_maker is not None:
            receipt_card_maker(
                track=track,
                diagnosis=diagnosis,
                gate_decision=gate,
                overlay_frames=overlay_frames or [],
                start_timestamp=start_timestamp,
                fps=fps,
                output_path=card_path,
            )
        crop_paths = write_track_crop_assets(track=track, receipts_dir=receipts_dir)
        existing_review_assets = ((existing_receipt_payloads or {}).get(track.track_id) or {}).get("review_assets") or {}
        payload = {
            "schema_version": "factory-track-receipt-v1",
            "track_id": track.track_id,
            "timestamps": {"first": track.first_timestamp, "last": track.last_timestamp},
            "evidence": asdict(track),
            "diagnosis": asdict(diagnosis) if diagnosis is not None else None,
            "perception_gate": asdict(gate) if gate is not None else None,
            "review_assets": {
                "overlay_sheet_path": _rel(overlay_sheet_path),
                "overlay_video_path": _rel(overlay_video_path),
                "track_sheet_path": _rel(card_path) if card_path.exists() else existing_review_assets.get("track_sheet_path"),
                "raw_crop_paths": [_rel(path) for path in crop_paths] or [str(path) for path in existing_review_assets.get("raw_crop_paths", [])],
            },
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        paths.append(path)
    return paths


def refresh_diagnostic_gate_receipts(*, diagnostic_path: Path) -> dict[str, Any]:
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    out_dir = diagnostic_path.parent
    receipt_paths = [
        path
        for raw_path in payload.get("track_receipts") or []
        if (path := resolve_repo_path(raw_path)) is not None and path.exists()
    ]
    if not receipt_paths:
        return payload
    existing_receipts = {path: json.loads(path.read_text(encoding="utf-8")) for path in receipt_paths}
    tracks = [track_evidence_from_payload(existing_receipts[path]) for path in receipt_paths]
    diagnoses = [diagnosis_from_payload(existing_receipts[path], fallback_track=track) for path, track in zip(receipt_paths, tracks)]
    existing_gate_rows = {}
    for row in payload.get("perception_gate") or []:
        if not isinstance(row, dict):
            continue
        try:
            existing_gate_rows[int(row.get("track_id") or 0)] = row
        except (TypeError, ValueError):
            continue
    gate_config = GateConfig()
    gate_decisions = evaluate_receipt_gate_decisions(
        tracks=tracks,
        receipt_paths=receipt_paths,
        gate_config=gate_config,
        fps=float(payload.get("fps") or 1.0),
        existing_gate_rows=existing_gate_rows,
    )

    overlay_sheet_path = resolve_repo_path(payload.get("overlay_sheet_path")) or (out_dir / "overlay_sheet.jpg")
    overlay_video_path = resolve_repo_path(payload.get("overlay_video_path")) or (out_dir / "overlay_video.mp4")
    receipt_payloads_by_track = {track.track_id: existing_receipts[path] for path, track in zip(receipt_paths, tracks)}
    rewritten_receipts = write_track_receipts(
        out_dir=out_dir,
        tracks=tracks,
        diagnoses=diagnoses,
        gate_decisions=gate_decisions,
        overlay_sheet_path=overlay_sheet_path,
        overlay_video_path=overlay_video_path,
        overlay_frames=[],
        start_timestamp=float(payload.get("start_timestamp") or 0.0),
        fps=float(payload.get("fps") or 1.0),
        receipt_card_maker=None,
        existing_receipt_payloads=receipt_payloads_by_track,
    )
    hard_negative_manifest_path = write_hard_negative_manifest(
        out_dir=out_dir,
        tracks=tracks,
        diagnoses=diagnoses,
        gate_decisions=gate_decisions,
        receipt_paths=rewritten_receipts,
    )
    if hard_negative_manifest_path is None:
        stale_manifest_path = out_dir / "hard_negative_manifest.json"
        if stale_manifest_path.exists():
            stale_manifest_path.unlink()

    result = {
        **payload,
        "track_receipts": [_rel(path) for path in rewritten_receipts],
        "track_receipt_cards": [
            _rel(path.with_name(f"{path.stem}-sheet.jpg"))
            for path in rewritten_receipts
            if path.with_name(f"{path.stem}-sheet.jpg").exists()
        ],
        "hard_negative_manifest_path": _rel(hard_negative_manifest_path) if hard_negative_manifest_path is not None else None,
        "diagnosis": [asdict(item) for item in diagnoses],
        "summary": summarize_diagnoses(diagnoses),
        "perception_gate": [asdict(item) for item in gate_decisions],
        "perception_gate_summary": summarize_gate_decisions(gate_decisions),
    }
    diagnostic_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def rebuild_diagnostic_from_metadata(*, diagnostic_path: Path) -> dict[str, Any]:
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    video_path = resolve_repo_path(payload.get("video_path"))
    calibration_path = resolve_repo_path(payload.get("calibration_path"))
    start_timestamp = payload.get("start_timestamp")
    end_timestamp = payload.get("end_timestamp")
    fps = payload.get("fps")
    if video_path is None or calibration_path is None or start_timestamp is None or end_timestamp is None or fps is None:
        return payload
    model_path = resolve_repo_path(payload.get("model_path"))
    person_model_path = resolve_repo_path(payload.get("person_model_path"))
    confidence = float(payload.get("confidence") or 0.20)
    return diagnose_event_window(
        video_path=video_path,
        calibration_path=calibration_path,
        out_dir=diagnostic_path.parent,
        start_timestamp=float(start_timestamp),
        end_timestamp=float(end_timestamp),
        fps=float(fps),
        model_path=model_path,
        person_model_path=person_model_path,
        confidence=confidence,
        force=True,
    )


def write_track_crop_assets(*, track: TrackEvidence, receipts_dir: Path, padding: float = 0.20) -> list[Path]:
    """Write raw crop/context assets for a track when representative observations exist."""
    observations = track.observations or []
    if not observations:
        return []
    try:
        import cv2
    except Exception:  # pragma: no cover - optional runtime dependency
        return []
    crop_dir = receipts_dir / f"track-{track.track_id:06d}-crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, observation in enumerate(observations):
        frame_path = resolve_repo_path(observation.get("frame_path"))
        box = observation.get("box_xywh")
        if frame_path is None or box is None:
            continue
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        crop = crop_with_padding(image, box, padding=padding)
        if crop is None:
            continue
        zone = str(observation.get("zone", "unknown")).replace("/", "-")
        output_path = crop_dir / f"crop-{index + 1:02d}-{zone}.jpg"
        if cv2.imwrite(str(output_path), crop):
            paths.append(output_path)
    return paths


def resolve_repo_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def crop_with_padding(image: Any, box_xywh: Any, *, padding: float) -> Any | None:
    try:
        x, y, width, height = [float(value) for value in box_xywh]
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    image_height, image_width = image.shape[:2]
    pad_x = width * padding
    pad_y = height * padding
    x1 = max(0, int(math.floor(x - pad_x)))
    y1 = max(0, int(math.floor(y - pad_y)))
    x2 = min(image_width, int(math.ceil(x + width + pad_x)))
    y2 = min(image_height, int(math.ceil(y + height + pad_y)))
    if x2 <= x1 or y2 <= y1:
        return None
    return image[y1:y2, x1:x2].copy()


def read_receipt_raw_crop_paths(receipt_path: Path) -> list[str]:
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    assets = payload.get("review_assets") or {}
    return [str(path) for path in assets.get("raw_crop_paths", [])]


def write_hard_negative_manifest(
    *,
    out_dir: Path,
    tracks: list[TrackEvidence],
    diagnoses: list[TrackDiagnosis],
    gate_decisions: list[Any],
    receipt_paths: list[Path],
) -> Path | None:
    """Write a manifest of rejected/uncertain false-positive evidence for retraining/audit."""
    diagnosis_by_track = {item.track_id: item for item in diagnoses}
    gate_by_track = {item.track_id: item for item in gate_decisions}
    receipt_by_track = {int(path.stem.split("-")[-1]): path for path in receipt_paths}
    items: list[dict[str, Any]] = []
    for track in sorted(tracks, key=lambda item: item.track_id):
        diagnosis = diagnosis_by_track.get(track.track_id)
        gate = gate_by_track.get(track.track_id)
        gate_decision = getattr(gate, "decision", None)
        diagnosis_decision = diagnosis.decision if diagnosis is not None else None
        if gate_decision == "allow_source_token" and diagnosis_decision != "reject":
            continue
        receipt_path = receipt_by_track.get(track.track_id)
        card_path = receipt_path.with_name(f"{receipt_path.stem}-sheet.jpg") if receipt_path is not None else None
        raw_crop_paths = read_receipt_raw_crop_paths(receipt_path) if receipt_path is not None else []
        reason = getattr(gate, "reason", None) or (diagnosis.reason if diagnosis is not None else "unknown")
        items.append(
            {
                "track_id": track.track_id,
                "label": "hard_negative" if gate_decision == "reject" or diagnosis_decision == "reject" else "uncertain_negative",
                "reason": reason,
                "gate_decision": asdict(gate) if gate is not None else None,
                "diagnosis": asdict(diagnosis) if diagnosis is not None else None,
                "evidence": asdict(track),
                "assets": {
                    "receipt_path": _rel(receipt_path) if receipt_path is not None else None,
                    "track_sheet_path": _rel(card_path) if card_path is not None and card_path.exists() else None,
                    "raw_crop_paths": raw_crop_paths,
                },
            }
        )
    if not items:
        return None
    path = out_dir / "hard_negative_manifest.json"
    payload = {
        "schema_version": "factory-hard-negative-manifest-v1",
        "source": "diagnose_event_window",
        "count": len(items),
        "items": items,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def make_track_receipt_card(
    *,
    track: TrackEvidence,
    diagnosis: TrackDiagnosis | None,
    gate_decision: Any,
    overlay_frames: list[Path],
    start_timestamp: float,
    fps: float,
    output_path: Path,
) -> Path | None:
    """Write a compact per-track JPG receipt for VLM/Oracle review."""
    if not overlay_frames:
        return None
    try:
        import cv2
        import numpy as np
    except Exception:  # pragma: no cover - optional runtime dependency
        return None

    selected_frames = select_track_overlay_frames(
        track=track,
        overlay_frames=overlay_frames,
        start_timestamp=start_timestamp,
        fps=fps,
    )
    images = []
    for label, frame_path in selected_frames:
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        image = resize_with_letterbox(image, width=420, height=260)
        cv2.putText(image, label, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(image, label, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 1, cv2.LINE_AA)
        images.append(image)
    if not images:
        return None
    while len(images) < 3:
        images.append(images[-1].copy())

    header = np.zeros((190, 1260, 3), dtype=np.uint8)
    decision = getattr(gate_decision, "decision", "unknown") if gate_decision is not None else "unknown"
    reason = getattr(gate_decision, "reason", None) or (diagnosis.reason if diagnosis is not None else "unknown")
    diagnosis_decision = diagnosis.decision if diagnosis is not None else "unknown"
    lines = [
        f"track {track.track_id:06d} | gate={decision} | reason={reason}",
        f"diagnosis={diagnosis_decision} | t={track.first_timestamp:.2f}-{track.last_timestamp:.2f}s | zones={','.join(track.zones_seen)}",
        (
            f"src={track.source_frames} out={track.output_frames} det={track.detections} "
            f"disp={track.max_displacement:.1f}px motion={track.max_internal_motion:.3f} "
            f"person={track.person_overlap_ratio:.2f} outside_person={track.outside_person_ratio:.2f}"
        ),
    ]
    for idx, line in enumerate(lines):
        cv2.putText(header, line[:150], (24, 46 + idx * 52), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    strip = np.hstack(images[:3])
    card = np.vstack([header, strip])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if cv2.imwrite(str(output_path), card):
        return output_path
    return None


def select_track_overlay_frames(
    *,
    track: TrackEvidence,
    overlay_frames: list[Path],
    start_timestamp: float,
    fps: float,
) -> list[tuple[str, Path]]:
    if not overlay_frames:
        return []
    midpoint = (track.first_timestamp + track.last_timestamp) / 2.0
    return [
        ("first/source-ish", overlay_frame_at_timestamp(overlay_frames, track.first_timestamp, start_timestamp=start_timestamp, fps=fps)),
        ("mid/high-evidence", overlay_frame_at_timestamp(overlay_frames, midpoint, start_timestamp=start_timestamp, fps=fps)),
        ("last/output-ish", overlay_frame_at_timestamp(overlay_frames, track.last_timestamp, start_timestamp=start_timestamp, fps=fps)),
    ]


def overlay_frame_at_timestamp(overlay_frames: list[Path], timestamp: float, *, start_timestamp: float, fps: float) -> Path:
    if not overlay_frames:
        raise ValueError("overlay_frames cannot be empty")
    safe_fps = fps if fps > 0 and math.isfinite(fps) else 1.0
    index = int(round((timestamp - start_timestamp) * safe_fps))
    index = max(0, min(len(overlay_frames) - 1, index))
    return overlay_frames[index]


def resize_with_letterbox(image: Any, *, width: int, height: int) -> Any:
    import cv2
    import numpy as np

    original_height, original_width = image.shape[:2]
    if original_width <= 0 or original_height <= 0:
        return np.zeros((height, width, 3), dtype=np.uint8)
    scale = min(width / original_width, height / original_height)
    resized_width = max(1, int(round(original_width * scale)))
    resized_height = max(1, int(round(original_height * scale)))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x_offset = (width - resized_width) // 2
    y_offset = (height - resized_height) // 2
    canvas[y_offset : y_offset + resized_height, x_offset : x_offset + resized_width] = resized
    return canvas


def summarize_diagnoses(diagnoses: list[TrackDiagnosis]) -> dict[str, Any]:
    counts: dict[str, int] = {"candidate": 0, "reject": 0, "uncertain": 0}
    reasons: dict[str, int] = {}
    for item in diagnoses:
        counts[item.decision] = counts.get(item.decision, 0) + 1
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    return {
        "track_count": len(diagnoses),
        "decision_counts": counts,
        "reason_counts": reasons,
        "has_source_to_output_candidate": counts.get("candidate", 0) > 0,
    }


def extract_dense_frames(*, video_path: Path, frames_dir: Path, start_timestamp: float, end_timestamp: float, fps: float) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration = end_timestamp - start_timestamp
    pattern = frames_dir / "frame_%06d.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_timestamp:.3f}",
            "-i",
            str(video_path.resolve()),
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"fps={fps:g}",
            str(pattern),
        ],
        check=True,
    )
    return sorted(frames_dir.glob("frame_*.jpg"))


def analyze_frames(
    *,
    frame_paths: list[Path],
    zones: CalibrationZones,
    overlay_dir: Path,
    start_timestamp: float,
    fps: float,
    model_path: Path | None,
    person_model_path: Path | None,
    confidence: float,
    tracker_match_distance: float,
) -> AnalysisArtifacts:
    try:
        import cv2
        import numpy as np
    except Exception as exc:  # pragma: no cover - runtime environment guard
        raise RuntimeError("diagnostics require cv2/numpy; use the repo .venv") from exc

    overlay_dir.mkdir(parents=True, exist_ok=True)
    tracker = SimpleBoxTracker(max_match_distance=tracker_match_distance, max_missing_frames=max(2, int(fps)))
    track_points: dict[int, list[tuple[float, float]]] = {}
    track_motion: dict[int, list[float]] = {}
    track_zones: dict[int, list[str]] = {}
    track_times: dict[int, list[float]] = {}
    track_detections: dict[int, int] = {}
    track_person_overlaps: dict[int, list[float]] = {}
    track_observations: dict[int, list[dict[str, Any]]] = {}
    overlay_frames: list[Path] = []
    yolo_model = load_yolo_model(model_path) if model_path else None
    person_model = load_yolo_model(person_model_path) if person_model_path else None
    previous_gray = None

    for index, frame_path in enumerate(frame_paths):
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        timestamp = start_timestamp + index / fps
        detections = detect_with_yolo_model(yolo_model, frame_path=frame_path, confidence=confidence) if yolo_model else []
        person_boxes = detect_person_boxes(person_model, frame_path=frame_path, confidence=0.20) if person_model else []
        tracks = tracker.update(detections)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        diff = None if previous_gray is None else cv2.absdiff(gray, previous_gray)
        previous_gray = gray

        draw_diagnostic_overlay(image=image, zones=zones)
        for person_box in person_boxes:
            px, py, pw, ph = [int(round(value)) for value in person_box]
            cv2.rectangle(image, (px, py), (px + pw, py + ph), (0, 0, 255), 2)
            cv2.putText(image, "person", (px, max(20, py - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
        for track in tracks:
            box = normalize_detection_box(track.bbox)
            center = box_center(box)
            zone = classify_point_zone(center, zones)
            motion = box_motion_fraction(diff, box) if diff is not None else 0.0
            person_overlap = max((box_overlap_fraction(box, person_box) for person_box in person_boxes), default=0.0)
            track_points.setdefault(track.track_id, []).append(center)
            track_motion.setdefault(track.track_id, []).append(motion)
            track_person_overlaps.setdefault(track.track_id, []).append(person_overlap)
            track_zones.setdefault(track.track_id, []).append(zone)
            track_times.setdefault(track.track_id, []).append(round(timestamp, 3))
            track_detections[track.track_id] = track_detections.get(track.track_id, 0) + 1
            track_observations.setdefault(track.track_id, []).append(
                {
                    "timestamp": round(timestamp, 3),
                    "frame_path": _rel(frame_path),
                    "box_xywh": [round(float(value), 3) for value in box],
                    "zone": zone,
                    "motion": round(float(motion), 6),
                    "person_overlap": round(float(person_overlap), 6),
                    "confidence": round(float(track.confidence), 6),
                }
            )
            color = (0, 255, 255) if zone == "source" else (0, 255, 0) if zone == "output" else (255, 128, 0)
            x1, y1, width, height = [int(round(value)) for value in box]
            x2 = x1 + width
            y2 = y1 + height
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
            cv2.putText(
                image,
                f"id={track.track_id} {zone} m={motion:.2f} p={person_overlap:.2f} c={track.confidence:.2f}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
                cv2.LINE_AA,
            )

        for points in track_points.values():
            for left, right in zip(points, points[1:]):
                cv2.line(image, (int(left[0]), int(left[1])), (int(right[0]), int(right[1])), (255, 255, 255), 2)

        cv2.putText(image, f"t={timestamp:.2f}s", (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3, cv2.LINE_AA)
        overlay_path = overlay_dir / f"overlay_{index + 1:06d}.jpg"
        cv2.imwrite(str(overlay_path), image)
        overlay_frames.append(overlay_path)

    evidence = build_track_evidence(
        track_points=track_points,
        track_motion=track_motion,
        track_zones=track_zones,
        track_times=track_times,
        track_detections=track_detections,
        track_person_overlaps=track_person_overlaps,
        track_observations=track_observations,
    )
    return AnalysisArtifacts(track_evidence=evidence, overlay_frames=overlay_frames, frame_count=len(frame_paths))


def load_yolo_model(model_path: Path | None) -> Any:
    if model_path is None:
        return None
    from ultralytics import YOLO

    return YOLO(str(model_path))


def detect_with_yolo_model(model: Any, *, frame_path: Path, confidence: float) -> list[dict[str, Any]]:
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


def detect_person_boxes(model: Any, *, frame_path: Path, confidence: float) -> list[Box]:
    results = model.predict(str(frame_path), conf=confidence, verbose=False, device="cpu", classes=[0])
    person_boxes: list[Box] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        xyxy_values = _to_list(getattr(boxes, "xyxy", []))
        for xyxy in xyxy_values:
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            if x2 > x1 and y2 > y1:
                person_boxes.append((x1, y1, x2 - x1, y2 - y1))
    return person_boxes


def build_track_evidence(
    *,
    track_points: dict[int, list[tuple[float, float]]],
    track_motion: dict[int, list[float]],
    track_zones: dict[int, list[str]],
    track_times: dict[int, list[float]],
    track_detections: dict[int, int],
    track_person_overlaps: dict[int, list[float]],
    track_observations: dict[int, list[dict[str, Any]]] | None = None,
) -> list[TrackEvidence]:
    evidence: list[TrackEvidence] = []
    for track_id, points in sorted(track_points.items()):
        zones = track_zones.get(track_id, [])
        motions = track_motion.get(track_id, [])
        times = track_times.get(track_id, [])
        unique_zones = []
        for zone in zones:
            if zone not in unique_zones:
                unique_zones.append(zone)
        max_displacement = 0.0
        for left in points:
            for right in points:
                max_displacement = max(max_displacement, _distance(left, right))
        static_location_ratio = calculate_static_location_ratio(points)
        flow_coherence = calculate_flow_coherence(points)
        output_ratio = (sum(1 for zone in zones if zone == "output") / len(zones)) if zones else 0.0
        static_stack_overlap_ratio = output_ratio if (zones[0] if zones else "unknown") == "output" or static_location_ratio > 0.5 else 0.0
        person_overlaps = track_person_overlaps.get(track_id, [])
        person_overlap_ratio = max(person_overlaps) if person_overlaps else 0.0
        evidence.append(
            TrackEvidence(
                track_id=track_id,
                first_timestamp=times[0] if times else 0.0,
                last_timestamp=times[-1] if times else 0.0,
                first_zone=zones[0] if zones else "unknown",
                zones_seen=unique_zones,
                source_frames=sum(1 for zone in zones if zone == "source"),
                output_frames=sum(1 for zone in zones if zone == "output"),
                max_displacement=round(max_displacement, 3),
                mean_internal_motion=round(sum(motions) / len(motions), 6) if motions else 0.0,
                max_internal_motion=round(max(motions), 6) if motions else 0.0,
                detections=track_detections.get(track_id, 0),
                static_location_ratio=round(static_location_ratio, 6),
                flow_coherence=round(flow_coherence, 6),
                static_stack_overlap_ratio=round(static_stack_overlap_ratio, 6),
                person_overlap_ratio=round(person_overlap_ratio, 6),
                outside_person_ratio=round(max(0.0, 1.0 - person_overlap_ratio), 6),
                observations=select_representative_observations((track_observations or {}).get(track_id, [])),
            )
        )
    return evidence


def select_representative_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_samples = 9
    if len(observations) <= max_samples:
        return observations
    last_index = len(observations) - 1
    indices = sorted({round(last_index * step / (max_samples - 1)) for step in range(max_samples)})
    return [observations[index] for index in indices]


def box_overlap_fraction(box: Box, other: Box) -> float:
    x1, y1, w1, h1 = box
    x2, y2, w2, h2 = other
    left = max(x1, x2)
    top = max(y1, y2)
    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)
    if right <= left or bottom <= top or w1 <= 0 or h1 <= 0:
        return 0.0
    return ((right - left) * (bottom - top)) / (w1 * h1)


def calculate_static_location_ratio(points: list[tuple[float, float]], *, radius: float = 18.0) -> float:
    if not points:
        return 0.0
    median_x = sorted(point[0] for point in points)[len(points) // 2]
    median_y = sorted(point[1] for point in points)[len(points) // 2]
    nearby = sum(1 for point in points if _distance(point, (median_x, median_y)) <= radius)
    return nearby / len(points)


def calculate_flow_coherence(points: list[tuple[float, float]]) -> float:
    vectors = [(right[0] - left[0], right[1] - left[1]) for left, right in zip(points, points[1:])]
    vectors = [vector for vector in vectors if math.hypot(vector[0], vector[1]) > 1e-6]
    if not vectors:
        return 0.0
    total_magnitude = sum(math.hypot(dx, dy) for dx, dy in vectors)
    net_dx = sum(dx for dx, _ in vectors)
    net_dy = sum(dy for _, dy in vectors)
    if total_magnitude <= 0:
        return 0.0
    return min(1.0, math.hypot(net_dx, net_dy) / total_magnitude)


def box_motion_fraction(diff: Any, box: Box, *, threshold: int = 24) -> float:
    if diff is None:
        return 0.0
    height, width = diff.shape[:2]
    x, y, width_box, height_box = [int(round(value)) for value in box]
    x1 = max(0, min(width - 1, x))
    x2 = max(0, min(width, x + width_box))
    y1 = max(0, min(height - 1, y))
    y2 = max(0, min(height, y + height_box))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    region = diff[y1:y2, x1:x2]
    if region.size == 0:
        return 0.0
    return float((region > threshold).sum() / region.size)


def draw_diagnostic_overlay(*, image: Any, zones: CalibrationZones) -> None:
    import cv2
    import numpy as np

    for polygon in zones.source_polygons:
        points = np.array([[int(x), int(y)] for x, y in polygon], dtype=np.int32)
        cv2.polylines(image, [points], True, (0, 255, 255), 3)
        cv2.putText(image, "SOURCE", tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    for polygon in zones.output_polygons:
        points = np.array([[int(x), int(y)] for x, y in polygon], dtype=np.int32)
        cv2.polylines(image, [points], True, (0, 255, 0), 3)
        cv2.putText(image, "OUTPUT", tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
    for polygon in zones.ignore_polygons:
        points = np.array([[int(x), int(y)] for x, y in polygon], dtype=np.int32)
        cv2.polylines(image, [points], True, (80, 80, 80), 2)


def make_overlay_media(*, overlay_frames: list[Path], sheet_path: Path, video_path: Path, fps: float) -> None:
    if not overlay_frames:
        sheet_path.write_text("no overlay frames", encoding="utf-8")
        video_path.write_text("no overlay frames", encoding="utf-8")
        return
    pattern = str(overlay_frames[0].parent / "overlay_%06d.jpg")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            f"{fps:g}",
            "-i",
            pattern,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-pattern_type",
            "glob",
            "-i",
            str(overlay_frames[0].parent / "overlay_*.jpg"),
            "-vf",
            "scale=360:-1:force_original_aspect_ratio=decrease,tile=5x4",
            "-frames:v",
            "1",
            str(sheet_path),
        ],
        check=True,
    )


def classify_point_zone(point: tuple[float, float], zones: CalibrationZones) -> str:
    if any(point_in_polygon(point, polygon) for polygon in zones.source_polygons):
        return "source"
    if any(point_in_polygon(point, polygon) for polygon in zones.output_polygons):
        return "output"
    if any(point_in_polygon(point, polygon) for polygon in zones.ignore_polygons):
        return "ignore"
    return "transfer"


def _normalize_polygons(raw_polygons: list[Any]) -> list[list[tuple[float, float]]]:
    polygons: list[list[tuple[float, float]]] = []
    for polygon in raw_polygons:
        points = [(float(point[0]), float(point[1])) for point in polygon]
        if len(points) >= 3:
            polygons.append(points)
    return polygons


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = diagnose_event_window(
        video_path=args.video,
        calibration_path=args.calibration,
        out_dir=args.out_dir,
        start_timestamp=args.start,
        end_timestamp=args.end,
        fps=args.fps,
        model_path=args.model,
        person_model_path=args.person_model,
        confidence=args.confidence,
        force=args.force,
        tracker_match_distance=args.tracker_match_distance,
        min_displacement=args.min_displacement,
        min_internal_motion=args.min_internal_motion,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.out_dir / 'diagnostic.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
