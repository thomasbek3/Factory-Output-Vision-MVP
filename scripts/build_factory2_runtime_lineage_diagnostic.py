#!/usr/bin/env python3
"""Build a runtime-lineage-backed proof diagnostic for a specific Factory2 event."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cv2

from app.core.settings import get_event_track_max_match_distance, get_person_conf_threshold
from app.services.counting import YoloObjectDetector
from app.services.person_detector import PersonDetector
from app.services.perception_gate import GateConfig, GateDecision, evaluate_track, summarize_gate_decisions
from app.services.runtime_event_counter import RuntimeEventCounter, load_runtime_calibration
from scripts.diagnose_event_window import (
    TrackDiagnosis,
    TrackEvidence,
    _distance,
    _rel,
    calculate_flow_coherence,
    calculate_static_location_ratio,
    classify_track_evidence,
    draw_diagnostic_overlay,
    extract_dense_frames,
    gate_features_from_track,
    make_overlay_media,
    make_track_receipt_card,
    resize_with_letterbox,
    select_representative_observations,
    summarize_diagnoses,
    write_track_receipts,
)

SCHEMA_VERSION = "factory2-runtime-lineage-diagnostic-v1"
CaptureFn = Callable[..., dict[str, Any]]
MediaMaker = Callable[..., None]
ReceiptCardMaker = Callable[..., Optional[Path]]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unique_zones(zones: list[str]) -> list[str]:
    output: list[str] = []
    for zone in zones:
        if zone not in output:
            output.append(zone)
    return output


def track_evidence_from_runtime_history(track_id: int, observations: list[dict[str, Any]]) -> TrackEvidence:
    ordered = sorted(observations, key=lambda item: float(item.get("timestamp") or 0.0))
    centers: list[tuple[float, float]] = []
    motions: list[float] = []
    zones: list[str] = []
    person_overlaps: list[float] = []
    outside_ratios: list[float] = []
    static_ratios: list[float] = []
    for observation in ordered:
        box = observation.get("box_xywh") or [0.0, 0.0, 0.0, 0.0]
        try:
            x, y, width, height = [float(value) for value in box]
        except (TypeError, ValueError):
            continue
        centers.append((x + width / 2.0, y + height / 2.0))
        zones.append(str(observation.get("zone") or "unknown"))
        try:
            motions.append(float(observation.get("motion") or 0.0))
        except (TypeError, ValueError):
            motions.append(0.0)
        try:
            person_overlaps.append(float(observation.get("person_overlap") or 0.0))
        except (TypeError, ValueError):
            person_overlaps.append(0.0)
        raw_outside = observation.get("outside_person_ratio")
        if raw_outside is None and person_overlaps:
            raw_outside = max(0.0, 1.0 - person_overlaps[-1])
        try:
            outside_ratios.append(float(raw_outside if raw_outside is not None else 1.0))
        except (TypeError, ValueError):
            outside_ratios.append(1.0)
        try:
            static_ratios.append(float(observation.get("static_stack_overlap_ratio") or 0.0))
        except (TypeError, ValueError):
            static_ratios.append(0.0)

    max_displacement = 0.0
    for left in centers:
        for right in centers:
            max_displacement = max(max_displacement, _distance(left, right))
    step_distances = [_distance(left, right) for left, right in zip(centers, centers[1:])]
    if not motions:
        motions = step_distances

    first_timestamp = float(ordered[0].get("timestamp") or 0.0) if ordered else 0.0
    last_timestamp = float(ordered[-1].get("timestamp") or 0.0) if ordered else 0.0
    representative = select_representative_observations(ordered)
    return TrackEvidence(
        track_id=track_id,
        first_timestamp=round(first_timestamp, 3),
        last_timestamp=round(last_timestamp, 3),
        first_zone=zones[0] if zones else "unknown",
        zones_seen=unique_zones(zones),
        source_frames=sum(1 for zone in zones if zone == "source"),
        output_frames=sum(1 for zone in zones if zone == "output"),
        max_displacement=round(max_displacement, 3),
        mean_internal_motion=round(sum(motions) / len(motions), 6) if motions else 0.0,
        max_internal_motion=round(max(motions), 6) if motions else 0.0,
        detections=len(ordered),
        static_location_ratio=round(calculate_static_location_ratio(centers), 6) if centers else 0.0,
        flow_coherence=round(calculate_flow_coherence(centers), 6) if centers else 0.0,
        static_stack_overlap_ratio=round(max(static_ratios), 6) if static_ratios else 0.0,
        person_overlap_ratio=round(max(person_overlaps), 6) if person_overlaps else 0.0,
        outside_person_ratio=round(min(outside_ratios), 6) if outside_ratios else 1.0,
        observations=representative,
    )


def hydrate_observation_frame_paths(
    *,
    histories: dict[str, list[dict[str, Any]]],
    video_path: Path,
    video_fps: float,
    frames_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    if video_fps <= 0 or not math.isfinite(video_fps):
        return histories
    frame_requests: dict[int, Path] = {}
    for observations in histories.values():
        for observation in observations:
            if observation.get("frame_path"):
                continue
            try:
                frame_index = max(0, int(round(float(observation.get("timestamp") or 0.0) * video_fps)))
            except (TypeError, ValueError):
                continue
            frame_requests.setdefault(frame_index, frames_dir / f"frame_{frame_index:06d}.jpg")
    if not frame_requests:
        return histories

    frames_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    for frame_index, frame_path in sorted(frame_requests.items()):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        cv2.imwrite(str(frame_path), frame)
    capture.release()

    hydrated: dict[str, list[dict[str, Any]]] = {}
    for track_id, observations in histories.items():
        hydrated_rows: list[dict[str, Any]] = []
        for observation in observations:
            row = dict(observation)
            if not row.get("frame_path"):
                try:
                    frame_index = max(0, int(round(float(row.get("timestamp") or 0.0) * video_fps)))
                except (TypeError, ValueError):
                    frame_index = None
                if frame_index is not None:
                    frame_path = frame_requests.get(frame_index)
                    if frame_path is not None and frame_path.exists():
                        row["frame_path"] = str(frame_path)
            hydrated_rows.append(row)
        hydrated[track_id] = hydrated_rows
    return hydrated


def make_media_from_frame_list(*, overlay_frames: list[Path], sheet_path: Path, video_path: Path, fps: float) -> None:
    if not overlay_frames:
        sheet_path.write_text("no runtime lineage frames", encoding="utf-8")
        video_path.write_text("no runtime lineage frames", encoding="utf-8")
        return
    images = []
    for frame_path in overlay_frames[:20]:
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        images.append(resize_with_letterbox(image, width=360, height=240))
    if not images:
        sheet_path.write_text("no readable runtime lineage frames", encoding="utf-8")
        video_path.write_text("no readable runtime lineage frames", encoding="utf-8")
        return
    while len(images) < 20:
        images.append(images[-1].copy())
    rows = []
    for index in range(0, 20, 5):
        rows.append(cv2.hconcat(images[index : index + 5]))
    sheet = cv2.vconcat(rows)
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(sheet_path), sheet)
    video_path.write_text("runtime-lineage diagnostic uses raw extracted frames", encoding="utf-8")


def runtime_gate_decision_for_track(
    *,
    track: TrackEvidence,
    event_row: dict[str, Any] | None,
    predecessor_track_ids: list[int],
) -> GateDecision:
    if event_row is None or int(event_row.get("track_id") or -1) != track.track_id:
        return evaluate_track(gate_features_from_track(track), GateConfig())

    gate_row = event_row.get("gate_decision") or {}
    merged_evidence = asdict(track)
    lineage_track_ids = list(predecessor_track_ids)
    source_track_id = event_row.get("source_track_id")
    try:
        normalized_source_track_id = int(source_track_id) if source_track_id is not None else None
    except (TypeError, ValueError):
        normalized_source_track_id = None
    if not lineage_track_ids and normalized_source_track_id is not None and normalized_source_track_id != track.track_id:
        lineage_track_ids = [normalized_source_track_id]
    if lineage_track_ids:
        merged_evidence["merged_predecessor_track_ids"] = lineage_track_ids
        merged_evidence["merged_predecessor_track_id"] = lineage_track_ids[-1]
    provenance_status = str(event_row.get("provenance_status") or "")
    if provenance_status:
        merged_evidence["runtime_provenance_status"] = provenance_status
    if event_row.get("source_token_id"):
        merged_evidence["runtime_source_token_id"] = str(event_row["source_token_id"])
    if normalized_source_track_id is not None:
        merged_evidence["runtime_source_track_id"] = normalized_source_track_id
    if event_row.get("chain_id"):
        merged_evidence["runtime_chain_id"] = str(event_row["chain_id"])
    if provenance_status == "synthetic_approved_chain_token":
        return GateDecision(
            track_id=track.track_id,
            decision="reject",
            reason="synthetic_runtime_fallback_token",
            flags=["runtime_lineage_not_proof_eligible", "synthetic_approved_chain_token"],
            evidence=merged_evidence,
        )
    return GateDecision(
        track_id=track.track_id,
        decision=str(gate_row.get("decision") or "allow_source_token"),
        reason=str(gate_row.get("reason") or "moving_panel_candidate"),
        flags=[str(flag) for flag in (gate_row.get("flags") or [])],
        evidence=merged_evidence,
    )


def build_runtime_lineage_diagnostic_from_capture(
    *,
    capture_payload: dict[str, Any],
    event_id: str | None,
    event_ts: float | None = None,
    event_tolerance_seconds: float = 0.2,
    out_dir: Path,
    force: bool,
    media_maker: MediaMaker | None = None,
    receipt_card_maker: ReceiptCardMaker | None = None,
) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            raise FileExistsError(out_dir)
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "track_receipts").mkdir(parents=True, exist_ok=True)

    event_row = None
    if event_id:
        event_row = next((item for item in capture_payload.get("events") or [] if str(item.get("event_id") or "") == event_id), None)
    if event_row is None and event_ts is not None:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for item in capture_payload.get("events") or []:
            try:
                distance = abs(float(item.get("event_ts")) - float(event_ts))
            except (TypeError, ValueError):
                continue
            if distance <= event_tolerance_seconds:
                candidates.append((distance, item))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            event_row = candidates[0][1]
    if event_row is None:
        raise ValueError(f"runtime event not found for event_id={event_id!r} event_ts={event_ts!r}")

    predecessor_track_ids = [int(value) for value in (event_row.get("predecessor_chain_track_ids") or [])]
    output_track_id = int(event_row.get("track_id") or 0)
    track_ids = predecessor_track_ids + [output_track_id]
    histories = capture_payload.get("track_histories") or {}
    selected_histories = {
        str(track_id): list(histories.get(str(track_id)) or histories.get(track_id) or [])
        for track_id in track_ids
    }
    video_path_value = capture_payload.get("video_path")
    if video_path_value:
        selected_histories = hydrate_observation_frame_paths(
            histories=selected_histories,
            video_path=Path(str(video_path_value)),
            video_fps=float(capture_payload.get("video_fps") or capture_payload.get("processing_fps") or capture_payload.get("fps") or 0.0),
            frames_dir=out_dir / "frames",
        )
    tracks = [
        track_evidence_from_runtime_history(int(track_id), list(selected_histories.get(str(track_id)) or []))
        for track_id in track_ids
    ]
    tracks = [track for track in tracks if track.detections > 0]
    if not tracks:
        raise ValueError(f"no runtime track history available for event_id={event_id}")

    diagnoses = [
        classify_track_evidence(
            track,
            min_displacement=GateConfig().min_displacement,
            min_internal_motion=GateConfig().min_internal_motion,
        )
        for track in tracks
    ]
    gate_decisions = [
        runtime_gate_decision_for_track(
            track=track,
            event_row=event_row,
            predecessor_track_ids=predecessor_track_ids,
        )
        for track in tracks
    ]

    overlay_frames = [Path(value) for value in (capture_payload.get("overlay_frames") or [])]
    if not overlay_frames:
        ordered_overlay_frames: list[Path] = []
        seen_overlay_frames: set[str] = set()
        for track in tracks:
            for observation in track.observations:
                frame_path = observation.get("frame_path")
                if not frame_path:
                    continue
                normalized = str(frame_path)
                if normalized in seen_overlay_frames:
                    continue
                seen_overlay_frames.add(normalized)
                ordered_overlay_frames.append(Path(normalized))
        overlay_frames = ordered_overlay_frames
    sheet_path = out_dir / "overlay_sheet.jpg"
    video_path = out_dir / "overlay_video.mp4"
    uses_overlay_sequence = bool(overlay_frames) and overlay_frames[0].name.startswith("overlay_")
    maker = media_maker or (make_overlay_media if uses_overlay_sequence else make_media_from_frame_list)
    maker(overlay_frames=overlay_frames, sheet_path=sheet_path, video_path=video_path, fps=float(capture_payload.get("fps") or 1.0))

    receipt_paths = write_track_receipts(
        out_dir=out_dir,
        tracks=tracks,
        diagnoses=diagnoses,
        gate_decisions=gate_decisions,
        overlay_sheet_path=sheet_path,
        overlay_video_path=video_path,
        overlay_frames=overlay_frames,
        start_timestamp=float(capture_payload.get("start_timestamp") or 0.0),
        fps=float(capture_payload.get("fps") or 1.0),
        receipt_card_maker=receipt_card_maker or make_track_receipt_card,
    )

    result = {
        "schema_version": "factory-event-diagnostic-v1",
        "runtime_lineage_schema_version": SCHEMA_VERSION,
        "runtime_event_id": str(event_row.get("event_id") or event_id or ""),
        "runtime_source_token_id": event_row.get("source_token_id"),
        "video_path": capture_payload.get("video_path"),
        "calibration_path": capture_payload.get("calibration_path"),
        "start_timestamp": float(capture_payload.get("start_timestamp") or 0.0),
        "end_timestamp": float(capture_payload.get("end_timestamp") or 0.0),
        "fps": float(capture_payload.get("fps") or 1.0),
        "model_path": capture_payload.get("model_path"),
        "person_model_path": capture_payload.get("person_model_path"),
        "frame_count": int(capture_payload.get("frame_count") or 0),
        "overlay_sheet_path": _rel(sheet_path),
        "overlay_video_path": _rel(video_path),
        "track_receipts": [_rel(path) for path in receipt_paths],
        "track_receipt_cards": [
            _rel(path.with_name(f"{path.stem}-sheet.jpg"))
            for path in receipt_paths
            if path.with_name(f"{path.stem}-sheet.jpg").exists()
        ],
        "diagnosis": [asdict(item) for item in diagnoses],
        "summary": summarize_diagnoses(diagnoses),
        "perception_gate": [asdict(item) for item in gate_decisions],
        "perception_gate_summary": summarize_gate_decisions(gate_decisions),
    }
    write_json(out_dir / "diagnostic.json", result)
    return result


def serialize_runtime_event(*, event_ts: float, event: Any, gate_decision: Any, provenance: dict[str, Any] | None = None, count_total: int) -> dict[str, Any]:
    payload = {
        "event_id": f"runtime-event-{int(round(event_ts * 1000.0))}",
        "event_ts": round(float(event_ts), 3),
        "track_id": int(event.track_id),
        "count_total": int(count_total),
        "reason": event.reason,
        "gate_decision": None
        if gate_decision is None
        else {
            "decision": gate_decision.decision,
            "reason": gate_decision.reason,
            "flags": list(gate_decision.flags),
        },
        "source_track_id": event.source_track_id,
        "source_token_id": event.source_token_id,
        "chain_id": event.chain_id,
    }
    if provenance:
        payload["predecessor_chain_track_ids"] = [int(value) for value in (provenance.get("predecessor_chain_track_ids") or [])]
        payload["source_bbox"] = provenance.get("source_bbox")
    return payload


def capture_runtime_lineage_window(
    *,
    video_path: Path,
    calibration_path: Path,
    out_dir: Path,
    start_timestamp: float,
    end_timestamp: float,
    fps: float,
    model_path: Path,
    person_model_path: Path,
    write_overlay_frames: bool = True,
) -> dict[str, Any]:
    zones, gate = load_runtime_calibration(calibration_path)
    frames_dir = out_dir / "frames"
    overlay_dir = out_dir / "overlays"
    frames_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = extract_dense_frames(
        video_path=video_path,
        frames_dir=frames_dir,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        fps=fps,
    )

    counter = RuntimeEventCounter(
        zones=zones,
        gate=gate,
        tracker_match_distance=get_event_track_max_match_distance(),
    )
    detector = YoloObjectDetector(model_path=str(model_path), conf_threshold=0.25, excluded_classes=[])
    person_detector = PersonDetector(get_person_conf_threshold())

    track_histories: dict[str, list[dict[str, Any]]] = {}
    overlay_frames: list[str] = []
    events: list[dict[str, Any]] = []
    for index, frame_path in enumerate(frame_paths):
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        timestamp = start_timestamp + (index / max(fps, 1.0))
        detection_result = detector.detect(image)
        detections = [{"box": item.bbox, "confidence": 1.0} for item in detection_result.detections]
        person_boxes = [(item.x, item.y, item.w, item.h) for item in person_detector.detect_people(image)]
        frame_result = counter.process_frame(frame=image, detections=detections, person_boxes=person_boxes)

        overlay_path = frame_path
        overlay = image.copy() if write_overlay_frames else None
        if overlay is not None:
            draw_diagnostic_overlay(image=overlay, zones=zones)
        for track in frame_result.tracks:
            x, y, width, height = [int(round(value)) for value in track.bbox]
            decision = frame_result.gate_decisions.get(track.track_id)
            color = (0, 255, 0) if decision is not None and decision.decision == "allow_source_token" else (0, 165, 255)
            if overlay is not None:
                cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)
                cv2.putText(
                    overlay,
                    f"t{track.track_id}:{frame_result.track_zones.get(track.track_id, 'unknown')}",
                    (x, max(20, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                    cv2.LINE_AA,
                )
            metadata = frame_result.track_metadata.get(track.track_id) or {}
            observation = {
                "timestamp": round(timestamp, 3),
                "box_xywh": [round(float(value), 3) for value in track.bbox],
                "confidence": round(float(track.confidence), 6),
                "zone": frame_result.track_zones.get(track.track_id, "unknown"),
                "motion": 0.0,
                "person_overlap": round(float(metadata.get("person_overlap_ratio", 0.0)), 6),
                "outside_person_ratio": round(float(metadata.get("outside_person_ratio", 1.0)), 6),
                "static_stack_overlap_ratio": round(
                    float(metadata.get("static_stack_overlap_ratio", metadata.get("static_overlap_ratio", 0.0))),
                    6,
                ),
                "frame_path": str(frame_path),
            }
            track_histories.setdefault(str(track.track_id), []).append(observation)

        if overlay is not None:
            overlay_path = overlay_dir / f"overlay_{index + 1:06d}.jpg"
            cv2.imwrite(str(overlay_path), overlay)
        overlay_frames.append(str(overlay_path))

        for event in frame_result.events:
            events.append(
                serialize_runtime_event(
                    event_ts=timestamp,
                    event=event,
                    gate_decision=frame_result.gate_decisions.get(event.track_id),
                    provenance=frame_result.event_provenance.get(event.track_id),
                    count_total=counter.total_count,
                )
            )

    return {
        "schema_version": "factory2-runtime-lineage-capture-v1",
        "video_path": _rel(video_path),
        "calibration_path": _rel(calibration_path),
        "model_path": _rel(model_path),
        "person_model_path": _rel(person_model_path),
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "fps": fps,
        "frame_count": len(frame_paths),
        "overlay_frames": overlay_frames,
        "events": events,
        "track_histories": track_histories,
    }


def build_runtime_lineage_diagnostic(
    *,
    video_path: Path,
    calibration_path: Path,
    out_dir: Path,
    start_timestamp: float,
    end_timestamp: float,
    fps: float,
    model_path: Path,
    person_model_path: Path,
    event_id: str | None,
    event_ts: float | None,
    force: bool,
    capture_fn: CaptureFn | None = None,
) -> dict[str, Any]:
    capture = capture_fn or capture_runtime_lineage_window
    capture_payload = capture(
        video_path=video_path,
        calibration_path=calibration_path,
        out_dir=out_dir,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        fps=fps,
        model_path=model_path,
        person_model_path=person_model_path,
    )
    write_json(out_dir / "runtime_lineage_capture.json", capture_payload)
    return build_runtime_lineage_diagnostic_from_capture(
        capture_payload=capture_payload,
        event_id=event_id,
        event_ts=event_ts,
        out_dir=out_dir,
        force=force,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a runtime-lineage-backed Factory2 proof diagnostic")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--person-model", type=Path, required=True)
    parser.add_argument("--event-id", type=str, default=None)
    parser.add_argument("--event-ts", type=float, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_runtime_lineage_diagnostic(
        video_path=args.video,
        calibration_path=args.calibration,
        out_dir=args.out_dir,
        start_timestamp=args.start,
        end_timestamp=args.end,
        fps=args.fps,
        model_path=args.model,
        person_model_path=args.person_model,
        event_id=args.event_id,
        event_ts=args.event_ts,
        force=args.force,
    )
    print(json.dumps({"output": str(args.out_dir / 'diagnostic.json'), "accepted_count": payload["perception_gate_summary"]["decision_counts"].get("allow_source_token", 0)}))


if __name__ == "__main__":
    main()
