from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

EXPORT_SCHEMA_VERSION = "factory-hard-negative-export-v1"
GENERATED_BY = "hard_negative_miner_v2"

FrameProvider = Callable[[Path, float], Any]
Detector = Callable[[Any], int]  # frame -> number of detections at/above the mining confidence


def mine_hard_negative_frames(
    *,
    model_path: Path,
    teacher_labels_path: Path,
    segment_manifest_path: Path,
    base_hard_negative_export_path: Path | None,
    work_dir: Path,
    output_export_path: Path,
    confidence: float = 0.2,
    sample_fps: float = 2.0,
    exclusion_margin_sec: float = 2.0,
    max_mined_frames: int = 80,
    detector: Detector | None = None,
    frame_provider: FrameProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Self-correction round: harvest the v1 model's false positives on the train footage.

    The whole train timeline is minable EXCEPT windows the teacher asserted a placement in
    (or was unclear about), each padded by a margin. Worker activity the teacher refuted is
    deliberately minable — that is exactly where transit false positives live.
    """
    if output_export_path.exists() and not force:
        raise FileExistsError(output_export_path)

    exclusions = _exclusion_intervals(teacher_labels_path)
    segments = _segments(segment_manifest_path)
    reader = frame_provider or _default_frame_provider()
    detect = detector or _default_detector(model_path, confidence)

    image_dir = work_dir / "images" / "train"
    label_dir = work_dir / "labels" / "train"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    mined_rows: list[dict[str, Any]] = []
    sampled_frames = 0
    for segment in segments:
        if len(mined_rows) >= max_mined_frames:
            break
        segment_id = str(segment.get("segment_id"))
        segment_path = Path(str(segment.get("path")))
        duration = float(segment.get("duration_sec") or 0.0)
        excluded = exclusions.get(segment_id, [])
        timestamp = 0.0
        while timestamp < duration and len(mined_rows) < max_mined_frames:
            if any(start - exclusion_margin_sec <= timestamp <= end + exclusion_margin_sec for start, end in excluded):
                timestamp += 1.0 / sample_fps
                continue
            try:
                frame = reader(segment_path, round(timestamp, 3))
            except Exception:  # noqa: BLE001 - unreadable frames are skipped, never fatal
                timestamp += 1.0 / sample_fps
                continue
            sampled_frames += 1
            if detect(frame) > 0:
                stem = f"mined-{len(mined_rows):04d}-{_safe_part(segment_id)}-{timestamp:.3f}s"
                image_path = image_dir / f"{stem}.jpg"
                label_path = label_dir / f"{stem}.txt"
                if _write_frame(image_path, frame):
                    label_path.write_text("", encoding="utf-8")
                    mined_rows.append(
                        {
                            "negative_id": stem,
                            "label": "hard_negative",
                            "reason": "model_false_positive_outside_asserted_event_windows",
                            "track_id": len(mined_rows) + 1,
                            "source_manifest": str(teacher_labels_path),
                            "source_asset_path": str(image_path),
                            "raw_crop_paths": [str(image_path)],
                            "exported_image_path": str(image_path),
                            "exported_label_path": str(label_path),
                            "yolo_class_name": "active_panel",
                            "yolo_label_contents": "",
                            "review_only": False,
                            "training_note": "Mined from the v1 model's false positives outside teacher-asserted windows.",
                            "evidence": {"segment_id": segment_id, "timestamp_sec": round(timestamp, 3)},
                            "gate_decision": None,
                            "diagnosis": None,
                        }
                    )
            timestamp += 1.0 / sample_fps

    base_rows: list[dict[str, Any]] = []
    base_manifests: list[str] = []
    if base_hard_negative_export_path is not None and base_hard_negative_export_path.exists():
        base_export = json.loads(base_hard_negative_export_path.read_text(encoding="utf-8"))
        base_rows = list(base_export.get("items") or [])
        base_manifests = list(base_export.get("source_manifests") or [])

    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "source_manifests": base_manifests + [str(teacher_labels_path)],
        "count": len(base_rows) + len(mined_rows),
        "include_uncertain": False,
        "write_yolo_negatives": True,
        "review_only": False,
        "mining": {
            "model_path": str(model_path),
            "confidence": confidence,
            "sample_fps": sample_fps,
            "exclusion_margin_sec": exclusion_margin_sec,
            "excluded_window_count": sum(len(rows) for rows in exclusions.values()),
            "sampled_frames": sampled_frames,
            "mined_count": len(mined_rows),
            "base_negative_count": len(base_rows),
        },
        "items": base_rows + mined_rows,
    }
    output_export_path.parent.mkdir(parents=True, exist_ok=True)
    output_export_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _exclusion_intervals(teacher_labels_path: Path) -> dict[str, list[tuple[float, float]]]:
    """Per-segment time intervals that may contain a placement: every non-refuted label's window."""
    labels_payload = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    intervals: dict[str, list[tuple[float, float]]] = {}
    for label in labels_payload.get("labels") or []:
        if str(label.get("verification_decision")) == "refute_completed":
            continue
        packet_manifest_path = label.get("source_packet_manifest_path")
        if not packet_manifest_path or not Path(str(packet_manifest_path)).exists():
            continue
        packet = json.loads(Path(str(packet_manifest_path)).read_text(encoding="utf-8"))
        window = packet.get("window") or {}
        start = window.get("start_offset_sec")
        end = window.get("end_offset_sec")
        if start is None or end is None:
            continue
        segment_id = str(packet.get("segment_id"))
        intervals.setdefault(segment_id, []).append((float(start), float(end)))
    return intervals


def _segments(segment_manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    return sorted(manifest.get("segments") or [], key=lambda row: str(row.get("path")))


def _default_detector(model_path: Path, confidence: float) -> Detector:
    state: dict[str, Any] = {}

    def _detect(frame: Any) -> int:
        if "model" not in state:
            from ultralytics import YOLO  # noqa: PLC0415

            state["model"] = YOLO(str(model_path))
        results = state["model"].predict(frame, conf=confidence, verbose=False)
        return sum(len(result.boxes) for result in results)

    return _detect


def _write_frame(path: Path, frame: Any) -> bool:
    import cv2  # noqa: PLC0415

    return bool(cv2.imwrite(str(path), frame))


def _default_frame_provider() -> FrameProvider:
    def _read(video_path: Path, timestamp_sec: float) -> Any:
        import cv2  # noqa: PLC0415

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"could not open video: {video_path}")
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s from {video_path}")
        return frame

    return _read


def _safe_part(value: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in value)
