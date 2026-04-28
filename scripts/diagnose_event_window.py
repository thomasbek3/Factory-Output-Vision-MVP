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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.calibration import Box, CalibrationZones, box_center, point_in_polygon
from app.services.perception_gate import GateConfig, GateTrackFeatures, evaluate_track, summarize_gate_decisions
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
                "track_sheet_path": _rel(card_path) if card_path.exists() else None,
            },
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        paths.append(path)
    return paths


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
            )
        )
    return evidence


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
