from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "auto-box-label-manifest-v1"
GENERATED_BY = "box_autolabeler_v2_placement_act"
SILVER_SCHEMA_VERSION = "factory-vision-silver-training-candidates-v1"

# Placement-act sampling: frames are labeled only inside this window around the event center,
# at this sampling rate, when the landing region differs from BOTH composites by at least
# the dissimilarity floor. The landing box is expanded so the part is covered while held.
ACT_WINDOW_SEC = 2.5
ACT_SAMPLE_FPS = 4.0
TRANSITION_MIN_DISSIMILARITY = 0.05
BOX_EXPAND_RATIO = 0.15

FrameProvider = Callable[[Path, float], Any]


def propose_auto_boxes(
    *,
    silver_dataset_path: Path,
    packet_manifest_path: Path,
    work_dir: Path,
    backend: str = "diff_box",
    class_name: str = "active_panel",
    frames_per_event: int = 3,
    replicate_span_sec: float = 3.0,
    min_box_area_ratio: float = 0.002,
    max_box_area_ratio: float = 0.5,
    global_motion_max_changed_ratio: float = 0.4,
    val_fraction: float = 0.15,
    class_prompt: str | None = None,
    yolo_world_model_path: Path | None = None,
    allow_model_download: bool = False,
    frame_provider: FrameProvider | None = None,
) -> dict[str, Any]:
    """Turn silver event candidates into bronze box labels for the existing review/assembly chain."""
    if backend not in {"diff_box", "yolo_world"}:
        raise ValueError(f"unknown box backend: {backend}")
    silver = json.loads(silver_dataset_path.read_text(encoding="utf-8"))
    if silver.get("schema_version") != SILVER_SCHEMA_VERSION:
        raise ValueError(f"expected silver dataset schema {SILVER_SCHEMA_VERSION}")
    packets = _packet_index(packet_manifest_path)
    reader = frame_provider or _default_frame_provider()
    detector = _detector_for_backend(
        backend,
        class_prompt=class_prompt or class_name,
        yolo_world_model_path=yolo_world_model_path,
        allow_model_download=allow_model_download,
    )

    items = list(silver.get("items") or [])
    packet_ids = sorted({str(item["packet_id"]) for item in items})
    splits = assign_event_splits(packet_ids, val_fraction=val_fraction)

    labels: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    frames_dir = work_dir / "frames"
    for item in items:
        packet_id = str(item["packet_id"])
        packet = packets.get(packet_id)
        if packet is None:
            skipped.append({"packet_id": packet_id, "reason": "packet_not_in_manifest"})
            continue
        result = _label_event(
            packet=packet,
            packet_id=packet_id,
            silver_item=item,
            reader=reader,
            detector=detector,
            backend=backend,
            class_name=class_name,
            split=splits[packet_id],
            frames_dir=frames_dir,
            frames_per_event=frames_per_event,
            replicate_span_sec=replicate_span_sec,
            min_box_area_ratio=min_box_area_ratio,
            max_box_area_ratio=max_box_area_ratio,
            global_motion_max_changed_ratio=global_motion_max_changed_ratio,
        )
        if isinstance(result, str):
            skipped.append({"packet_id": packet_id, "reason": result})
        else:
            labels.extend(result)

    split_histogram: dict[str, int] = {}
    for label in labels:
        split = str(label["metadata"]["split"])
        split_histogram[split] = split_histogram.get(split, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "station_id": _station_id(packets),
        "backend": backend,
        "backend_params": {
            "frames_per_event": frames_per_event,
            "replicate_span_sec": replicate_span_sec,
            "min_box_area_ratio": min_box_area_ratio,
            "max_box_area_ratio": max_box_area_ratio,
            "global_motion_max_changed_ratio": global_motion_max_changed_ratio,
            "act_window_sec": ACT_WINDOW_SEC,
            "act_sample_fps": ACT_SAMPLE_FPS,
            "transition_min_dissimilarity": TRANSITION_MIN_DISSIMILARITY,
            "box_expand_ratio": BOX_EXPAND_RATIO,
            "val_fraction": val_fraction,
            "class_prompt": class_prompt if backend == "yolo_world" else None,
        },
        "source_silver_dataset_path": str(silver_dataset_path),
        "source_packet_manifest_path": str(packet_manifest_path),
        "label_authority_tier": "bronze",
        "refuses_validation_truth": True,
        "validation_truth_eligible": False,
        "labels": labels,
        "summary": {
            "events_in": len(items),
            "events_with_box": len({label["metadata"]["packet_id"] for label in labels}),
            "label_count": len(labels),
            "skipped": skipped,
            "split_histogram": split_histogram,
        },
    }


def write_auto_box_manifest(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assign_event_splits(packet_ids: list[str], *, val_fraction: float, min_val_events: int = 1) -> dict[str, str]:
    """Deterministic event-granular split: all frames of one packet share one split."""
    if not packet_ids:
        return {}
    ordered = sorted(packet_ids, key=lambda pid: hashlib.sha1(pid.encode("utf-8")).hexdigest())
    val_count = 0
    if len(ordered) >= 2 and val_fraction > 0:
        val_count = max(min_val_events, round(len(ordered) * val_fraction))
        val_count = min(val_count, len(ordered) - 1)
    val_ids = set(ordered[:val_count])
    return {pid: ("val" if pid in val_ids else "train") for pid in sorted(packet_ids)}


def _label_event(
    *,
    packet: dict[str, Any],
    packet_id: str,
    silver_item: dict[str, Any],
    reader: FrameProvider,
    detector: Callable[..., Any],
    backend: str,
    class_name: str,
    split: str,
    frames_dir: Path,
    frames_per_event: int,
    replicate_span_sec: float,
    min_box_area_ratio: float,
    max_box_area_ratio: float,
    global_motion_max_changed_ratio: float,
) -> list[dict[str, Any]] | str:
    window = packet.get("window") or {}
    segment_path = Path(str(packet.get("segment_path")))
    before_sec = float(window.get("before_sec") if window.get("before_sec") is not None else window.get("start_offset_sec") or 0.0)
    after_sec = float(window.get("after_sec") if window.get("after_sec") is not None else window.get("end_offset_sec") or 0.0)

    # Median composites across a few seconds erase the (moving) worker but keep the static
    # placed part, so the diff box outlines what stayed, not who walked through the frame.
    half_span = max(0.5, replicate_span_sec / 2.0)
    before_timestamps = [max(0.0, before_sec - replicate_span_sec), max(0.0, before_sec - half_span), before_sec]
    after_timestamps = [after_sec, after_sec + half_span, after_sec + replicate_span_sec]
    try:
        before_frame = _median_frame(reader, segment_path, before_timestamps)
        after_frame = _median_frame(reader, segment_path, after_timestamps)
    except Exception:  # noqa: BLE001 - unreadable frames skip the event, never abort the run
        return "frame_read_failed"

    proposal = detector(
        before_frame=before_frame,
        after_frame=after_frame,
        min_box_area_ratio=min_box_area_ratio,
        max_box_area_ratio=max_box_area_ratio,
        global_motion_max_changed_ratio=global_motion_max_changed_ratio,
    )
    if isinstance(proposal, str):
        return proposal
    landing_box, confidence, diff_score = proposal

    import cv2  # noqa: PLC0415 - heavy import stays lazy

    height, width = after_frame.shape[:2]
    # The class semantic is the part DURING placement (like the verified panel_in_transit
    # runtime), never the settled part: a resting part is pixel-identical to the unlabeled
    # stack around it, which poisons training with contradictory supervision.
    box = _expand_box(landing_box, width=width, height=height, ratio=BOX_EXPAND_RATIO)
    before_patch = _box_patch(before_frame, box)
    after_patch = _box_patch(after_frame, box)
    center_sec = float(window.get("center_offset_sec") or (before_sec + after_sec) / 2.0)
    act_start = max(before_sec, center_sec - ACT_WINDOW_SEC)
    act_end = min(after_sec, center_sec + ACT_WINDOW_SEC)

    candidates: list[tuple[float, float, Any]] = []
    timestamp_sec = act_start
    while timestamp_sec <= act_end + 1e-9:
        try:
            frame = reader(segment_path, round(timestamp_sec, 3))
        except Exception:  # noqa: BLE001
            timestamp_sec += 1.0 / ACT_SAMPLE_FPS
            continue
        patch = _box_patch(frame, box)
        diff_vs_before = 1.0 - _patch_similarity(before_patch, patch)
        diff_vs_after = 1.0 - _patch_similarity(after_patch, patch)
        transition_score = min(diff_vs_before, diff_vs_after)
        # A placement-act frame differs from BOTH the empty before-state and the settled
        # after-state of the landing region; settled or empty frames are never labeled.
        if transition_score >= TRANSITION_MIN_DISSIMILARITY:
            candidates.append((transition_score, round(timestamp_sec, 3), frame))
        timestamp_sec += 1.0 / ACT_SAMPLE_FPS

    candidates.sort(key=lambda row: (-row[0], row[1]))
    event_dir = frames_dir / _safe_part(packet_id)
    event_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for frame_index, (transition_score, timestamp_sec, frame) in enumerate(candidates[: max(1, frames_per_event)]):
        frame_path = event_dir / f"frame_{timestamp_sec:.3f}s.jpg"
        if not cv2.imwrite(str(frame_path), frame):
            continue
        rows.append(
            {
                "label_id": f"{packet_id}-auto-{frame_index:02d}",
                "frame_id": f"{packet_id}-{timestamp_sec:.3f}s",
                "image_width": int(width),
                "image_height": int(height),
                "class_name": class_name,
                "box": [round(float(value), 2) for value in box],
                "confidence": confidence,
                "source_type": "box",
                "metadata": {
                    "frame_path": str(frame_path),
                    "video_path": str(segment_path),
                    "timestamp_seconds": timestamp_sec,
                    "packet_id": packet_id,
                    "window_id": packet.get("window_id"),
                    "station_id": packet.get("station_id"),
                    "split": split,
                    "backend": backend,
                    "diff_stability_score": round(transition_score, 4),
                    "diff_changed_score": round(diff_score, 4),
                    "label_semantic": "part_during_placement",
                    "label_authority_tier": "bronze",
                    "source_silver_item_id": silver_item.get("item_id"),
                    "training_provenance": (packet.get("source_proposal") or {}).get(
                        "training_provenance"
                    ),
                },
            }
        )
    if not rows:
        return "no_transition_frames"
    return rows


def _diff_box_detector(
    *,
    before_frame: Any,
    after_frame: Any,
    min_box_area_ratio: float,
    max_box_area_ratio: float,
    global_motion_max_changed_ratio: float,
) -> tuple[tuple[float, float, float, float], None, float] | str:
    """Box around the largest stable region that changed between the before and after frames."""
    import cv2  # noqa: PLC0415

    if before_frame.shape[:2] != after_frame.shape[:2]:
        after_frame = cv2.resize(after_frame, (before_frame.shape[1], before_frame.shape[0]), interpolation=cv2.INTER_AREA)
    height, width = after_frame.shape[:2]
    diff = cv2.absdiff(before_frame, after_frame)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    changed_ratio = float((mask > 0).sum()) / float(mask.size)
    if changed_ratio > global_motion_max_changed_ratio:
        return "global_motion"
    if changed_ratio == 0.0:
        return "no_visible_change"

    kernel_size = max(3, (width // 100) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return "no_visible_change"
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    box = (
        max(0.0, float(x)),
        max(0.0, float(y)),
        min(float(width), float(x + w)),
        min(float(height), float(y + h)),
    )
    area_ratio = ((box[2] - box[0]) * (box[3] - box[1])) / float(width * height)
    if area_ratio < min_box_area_ratio:
        return "box_too_small"
    if area_ratio > max_box_area_ratio:
        return "box_too_large"
    return box, None, changed_ratio


def _detector_for_backend(
    backend: str,
    *,
    class_prompt: str,
    yolo_world_model_path: Path | None,
    allow_model_download: bool,
) -> Callable[..., Any]:
    if backend == "diff_box":
        return _diff_box_detector
    if yolo_world_model_path is None and not allow_model_download:
        raise ValueError(
            "yolo_world backend needs --yolo-world-model pointing at local weights, "
            "or explicit --allow-model-download"
        )

    def _yolo_world_detector(
        *,
        before_frame: Any,
        after_frame: Any,
        min_box_area_ratio: float,
        max_box_area_ratio: float,
        global_motion_max_changed_ratio: float,
    ) -> tuple[tuple[float, float, float, float], float | None, float] | str:
        del before_frame, global_motion_max_changed_ratio
        from ultralytics import YOLOWorld  # noqa: PLC0415

        model = YOLOWorld(str(yolo_world_model_path) if yolo_world_model_path else "yolov8s-worldv2.pt")
        model.set_classes([class_prompt])
        results = model.predict(after_frame, verbose=False)
        height, width = after_frame.shape[:2]
        best: tuple[tuple[float, float, float, float], float] | None = None
        for result in results:
            for row in result.boxes:
                confidence = float(row.conf[0])
                x1, y1, x2, y2 = (float(value) for value in row.xyxy[0])
                if best is None or confidence > best[1]:
                    best = ((max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2)), confidence)
        if best is None:
            return "no_detection"
        box, confidence = best
        area_ratio = ((box[2] - box[0]) * (box[3] - box[1])) / float(width * height)
        if area_ratio < min_box_area_ratio:
            return "box_too_small"
        if area_ratio > max_box_area_ratio:
            return "box_too_large"
        return box, confidence, 0.0

    return _yolo_world_detector


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


def _packet_index(packet_manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
    index: dict[str, dict[str, Any]] = {}
    for row in manifest.get("packets") or []:
        manifest_path = Path(str(row.get("packet_manifest_path")))
        if not manifest_path.exists():
            continue
        packet = json.loads(manifest_path.read_text(encoding="utf-8"))
        index[str(packet.get("packet_id"))] = packet
    return index


def _station_id(packets: dict[str, dict[str, Any]]) -> str:
    for packet in packets.values():
        station_id = packet.get("station_id")
        if station_id:
            return str(station_id)
    return "unknown"


def _expand_box(
    box: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
    ratio: float,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    dx = (x2 - x1) * ratio
    dy = (y2 - y1) * ratio
    return (
        max(0.0, x1 - dx),
        max(0.0, y1 - dy),
        min(float(width), x2 + dx),
        min(float(height), y2 + dy),
    )


def _median_frame(reader: FrameProvider, video_path: Path, timestamps: list[float]) -> Any:
    import numpy as np  # noqa: PLC0415

    frames = []
    for timestamp_sec in timestamps:
        try:
            frames.append(reader(video_path, timestamp_sec))
        except Exception:  # noqa: BLE001 - a missing sample shrinks the composite, never aborts
            continue
    if not frames:
        raise RuntimeError(f"no readable frames for median composite near {timestamps} in {video_path}")
    if len(frames) == 1:
        return frames[0]
    base_shape = frames[0].shape
    frames = [frame for frame in frames if frame.shape == base_shape]
    return np.median(np.stack(frames), axis=0).astype(frames[0].dtype)


def _box_patch(frame: Any, box: tuple[float, float, float, float]) -> Any:
    x1, y1, x2, y2 = (int(round(value)) for value in box)
    return frame[max(0, y1) : max(0, y2), max(0, x1) : max(0, x2)]


def _patch_similarity(reference: Any, candidate: Any) -> float:
    import cv2  # noqa: PLC0415

    if reference.size == 0 or candidate.size == 0:
        return 0.0
    if reference.shape != candidate.shape:
        candidate = cv2.resize(candidate, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_AREA)
    mean_abs_diff = float(cv2.absdiff(reference, candidate).mean())
    return 1.0 - mean_abs_diff / 255.0


def _safe_part(value: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in value)
