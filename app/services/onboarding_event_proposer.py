from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.stream_recorder import validate_segment_manifest


SCHEMA_VERSION = "factory-vision-onboarding-event-proposals-v1"
GENERATED_BY = "motion_event_proposer_v2"
PROPOSAL_MODES = {"full_frame_motion", "output_zone_motion"}


def build_event_proposals(
    *,
    segment_manifest_path: Path,
    sample_fps: float = 2.0,
    motion_threshold: float = 0.025,
    output_zone_polygon: list[list[float]] | None = None,
    proposal_mode: str = "full_frame_motion",
    zone_motion_threshold: float = 0.04,
    min_cluster_gap_sec: float = 1.0,
    window_before_sec: float = 4.0,
    window_after_sec: float = 4.0,
    stable_negative_count: int = 2,
) -> dict[str, Any]:
    """Build advisory event proposals from recorded segments.

    This is an onboarding helper only. It does not count parts, call a teacher,
    train a model, or change runtime totals.
    """

    _validate_config(
        sample_fps=sample_fps,
        motion_threshold=motion_threshold,
        proposal_mode=proposal_mode,
        zone_motion_threshold=zone_motion_threshold,
        output_zone_polygon=output_zone_polygon,
        min_cluster_gap_sec=min_cluster_gap_sec,
        window_before_sec=window_before_sec,
        window_after_sec=window_after_sec,
        stable_negative_count=stable_negative_count,
    )
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    validate_segment_manifest(manifest)
    station_id = str(manifest["station_id"])
    proposals: list[dict[str, Any]] = []
    segment_summaries: list[dict[str, Any]] = []
    for segment in manifest["segments"]:
        if not segment.get("decode_ok"):
            segment_summaries.append(
                {
                    "segment_id": segment.get("segment_id"),
                    "status": "skipped_decode_not_ok",
                    "proposal_count": 0,
                    "sample_count": 0,
                }
            )
            continue
        segment_path = _resolve_segment_path(segment_manifest_path=segment_manifest_path, segment=segment)
        samples = sample_segment_motion(
            video_path=segment_path,
            sample_fps=sample_fps,
            duration_sec=float(segment["duration_sec"]),
            output_zone_polygon=output_zone_polygon,
        )
        segment_proposals = build_motion_event_proposals_from_samples(
            station_id=station_id,
            segment=segment,
            samples=samples,
            motion_threshold=motion_threshold,
            proposal_mode=proposal_mode,
            zone_motion_threshold=zone_motion_threshold,
            min_cluster_gap_sec=min_cluster_gap_sec,
            window_before_sec=window_before_sec,
            window_after_sec=window_after_sec,
            stable_negative_count=stable_negative_count,
        )
        proposals.extend(segment_proposals)
        segment_summaries.append(
            {
                "segment_id": segment["segment_id"],
                "status": "processed",
                "proposal_count": len(segment_proposals),
                "event_proposal_count": len(
                    [proposal for proposal in segment_proposals if proposal["candidate_type"] == "event_candidate"]
                ),
                "stable_negative_count": len(
                    [
                        proposal
                        for proposal in segment_proposals
                        if proposal["candidate_type"] == "hard_negative_candidate"
                    ]
                ),
                "sample_count": len(samples),
                "max_motion_score": round(max((float(sample["motion_score"]) for sample in samples), default=0.0), 6),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "station_id": station_id,
        "segment_manifest_path": str(segment_manifest_path),
        "generated_by": GENERATED_BY,
        "privacy_mode": manifest.get("privacy_mode", "offline_local"),
        "config": {
            "sample_fps": float(sample_fps),
            "motion_threshold": float(motion_threshold),
            "proposal_mode": proposal_mode,
            "zone_motion_threshold": float(zone_motion_threshold),
            "output_zone_polygon": output_zone_polygon,
            "min_cluster_gap_sec": float(min_cluster_gap_sec),
            "window_before_sec": float(window_before_sec),
            "window_after_sec": float(window_after_sec),
            "stable_negative_count": int(stable_negative_count),
        },
        "refuses_validation_truth": True,
        "proposals": proposals,
        "summary": {
            "segment_count": len(manifest["segments"]),
            "processed_segment_count": len([row for row in segment_summaries if row["status"] == "processed"]),
            "proposal_count": len(proposals),
            "event_proposal_count": len(
                [proposal for proposal in proposals if proposal["candidate_type"] == "event_candidate"]
            ),
            "stable_negative_count": len(
                [proposal for proposal in proposals if proposal["candidate_type"] == "hard_negative_candidate"]
            ),
            "segments": segment_summaries,
        },
    }


def build_motion_event_proposals_from_samples(
    *,
    station_id: str,
    segment: dict[str, Any],
    samples: list[dict[str, Any]],
    motion_threshold: float,
    proposal_mode: str = "full_frame_motion",
    zone_motion_threshold: float = 0.04,
    min_cluster_gap_sec: float = 1.0,
    window_before_sec: float = 4.0,
    window_after_sec: float = 4.0,
    stable_negative_count: int = 0,
) -> list[dict[str, Any]]:
    duration_sec = _positive_float(segment.get("duration_sec"), name="duration_sec")
    score_key = _score_key_for_mode(proposal_mode)
    threshold = zone_motion_threshold if proposal_mode == "output_zone_motion" else motion_threshold
    clusters = _motion_clusters(
        samples=samples,
        motion_threshold=threshold,
        min_cluster_gap_sec=min_cluster_gap_sec,
        score_key=score_key,
    )
    proposals: list[dict[str, Any]] = []
    occupied_windows: list[tuple[float, float]] = []
    for index, cluster in enumerate(clusters, start=1):
        peak = max(cluster, key=lambda sample: float(sample.get(score_key) or 0.0))
        center_sec = float(peak["timestamp_sec"])
        reasons = ["frame_motion_above_threshold"]
        if proposal_mode == "output_zone_motion":
            reasons.append("output_zone_motion_above_threshold")
        proposal = _build_proposal(
            station_id=station_id,
            segment=segment,
            index=index,
            candidate_type="event_candidate",
            proposal_type="motion_burst",
            center_sec=center_sec,
            duration_sec=duration_sec,
            window_before_sec=window_before_sec,
            window_after_sec=window_after_sec,
            candidate_reasons=reasons,
            motion_summary={
                "peak_motion_score": round(float(peak["motion_score"]), 6),
                "peak_motion_score_output_zone": _rounded_optional(peak.get("motion_score_output_zone")),
                "cluster_start_sec": round(float(cluster[0]["timestamp_sec"]), 3),
                "cluster_end_sec": round(float(cluster[-1]["timestamp_sec"]), 3),
                "cluster_sample_count": len(cluster),
                "stable_before_sec": _nearest_stable_timestamp(
                    samples=samples,
                    center_sec=center_sec,
                    direction="before",
                    stable_threshold=threshold * 0.5,
                    score_key=score_key,
                ),
                "stable_after_sec": _nearest_stable_timestamp(
                    samples=samples,
                    center_sec=center_sec,
                    direction="after",
                    stable_threshold=threshold * 0.5,
                    score_key=score_key,
                ),
            },
        )
        proposals.append(proposal)
        occupied_windows.append((float(proposal["start_offset_sec"]), float(proposal["end_offset_sec"])))
    proposals.extend(
        _stable_negative_proposals(
            station_id=station_id,
            segment=segment,
            samples=samples,
            occupied_windows=occupied_windows,
            count=stable_negative_count,
            duration_sec=duration_sec,
            window_before_sec=window_before_sec,
            window_after_sec=window_after_sec,
            stable_threshold=threshold * 0.5,
            score_key=score_key,
        )
    )
    return proposals


def sample_segment_motion(
    *,
    video_path: Path,
    sample_fps: float,
    duration_sec: float,
    output_zone_polygon: list[list[float]] | None = None,
) -> list[dict[str, Any]]:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("motion event proposal requires cv2; use the repo .venv") from exc
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open segment video: {video_path}")
    samples: list[dict[str, Any]] = []
    previous_gray: Any | None = None
    mask: Any | None = None
    zone_pixel_count: int | None = None
    try:
        for timestamp_sec in _sample_timestamps(duration_sec=duration_sec, sample_fps=sample_fps):
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(_resize_for_motion(frame), cv2.COLOR_BGR2GRAY)
            if output_zone_polygon is not None and mask is None:
                mask = _build_polygon_mask(cv2=cv2, frame_shape=gray.shape, polygon=output_zone_polygon)
                zone_pixel_count = int(cv2.countNonZero(mask))
                if zone_pixel_count <= 0:
                    raise ValueError("output_zone_polygon produced an empty mask")
            if previous_gray is None:
                motion_score = 0.0
                zone_motion_score = 0.0 if mask is not None else None
            else:
                diff = cv2.absdiff(previous_gray, gray)
                motion_score = float(diff.mean()) / 255.0
                zone_motion_score = (
                    float(cv2.sumElems(cv2.bitwise_and(diff, diff, mask=mask))[0]) / float(zone_pixel_count) / 255.0
                    if mask is not None and zone_pixel_count
                    else None
                )
            row = {
                "timestamp_sec": round(timestamp_sec, 3),
                "motion_score": round(motion_score, 6),
            }
            if zone_motion_score is not None:
                row["motion_score_output_zone"] = round(zone_motion_score, 6)
            samples.append(row)
            previous_gray = gray
    finally:
        capture.release()
    return samples


def write_event_proposals(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_config(
    *,
    sample_fps: float,
    motion_threshold: float,
    proposal_mode: str,
    zone_motion_threshold: float,
    output_zone_polygon: list[list[float]] | None,
    min_cluster_gap_sec: float,
    window_before_sec: float,
    window_after_sec: float,
    stable_negative_count: int,
) -> None:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if motion_threshold <= 0:
        raise ValueError("motion_threshold must be positive")
    if proposal_mode not in PROPOSAL_MODES:
        raise ValueError(f"proposal_mode must be one of {sorted(PROPOSAL_MODES)}")
    if zone_motion_threshold <= 0:
        raise ValueError("zone_motion_threshold must be positive")
    if proposal_mode == "output_zone_motion" and output_zone_polygon is None:
        raise ValueError("output_zone_motion mode requires output_zone_polygon")
    if output_zone_polygon is not None:
        _validate_polygon(output_zone_polygon, name="output_zone_polygon")
    if min_cluster_gap_sec <= 0:
        raise ValueError("min_cluster_gap_sec must be positive")
    if window_before_sec < 0:
        raise ValueError("window_before_sec must be non-negative")
    if window_after_sec < 0:
        raise ValueError("window_after_sec must be non-negative")
    if window_before_sec == 0 and window_after_sec == 0:
        raise ValueError("at least one window side must be positive")
    if stable_negative_count < 0:
        raise ValueError("stable_negative_count must be non-negative")


def _resolve_segment_path(*, segment_manifest_path: Path, segment: dict[str, Any]) -> Path:
    raw_path = Path(str(segment["path"])).expanduser()
    if raw_path.is_absolute():
        return raw_path
    return (segment_manifest_path.parent / raw_path).resolve()


def _positive_float(value: Any, *, name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _sample_timestamps(*, duration_sec: float, sample_fps: float) -> list[float]:
    step = 1.0 / sample_fps
    timestamps: list[float] = []
    current = 0.0
    while current <= duration_sec:
        timestamps.append(round(current, 6))
        current += step
    if not timestamps or timestamps[-1] < duration_sec:
        timestamps.append(round(duration_sec, 6))
    return timestamps


def _resize_for_motion(frame: Any, *, max_width: int = 640) -> Any:
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("motion event proposal requires cv2; use the repo .venv") from exc
    scale = max_width / float(width)
    return cv2.resize(frame, (max_width, max(1, int(round(height * scale)))), interpolation=cv2.INTER_AREA)


def _motion_clusters(
    *,
    samples: list[dict[str, Any]],
    motion_threshold: float,
    min_cluster_gap_sec: float,
    score_key: str = "motion_score",
) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    last_motion_ts: float | None = None
    for sample in samples:
        score = float(sample.get(score_key) or 0.0)
        if score < motion_threshold:
            continue
        timestamp_sec = float(sample["timestamp_sec"])
        if last_motion_ts is not None and timestamp_sec - last_motion_ts > min_cluster_gap_sec and current:
            clusters.append(current)
            current = []
        current.append(sample)
        last_motion_ts = timestamp_sec
    if current:
        clusters.append(current)
    return clusters


def _build_proposal(
    *,
    station_id: str,
    segment: dict[str, Any],
    index: int,
    candidate_type: str,
    proposal_type: str,
    center_sec: float,
    duration_sec: float,
    window_before_sec: float,
    window_after_sec: float,
    candidate_reasons: list[str],
    motion_summary: dict[str, Any],
) -> dict[str, Any]:
    start_sec = max(0.0, center_sec - window_before_sec)
    end_sec = min(duration_sec, center_sec + window_after_sec)
    if end_sec <= start_sec:
        end_sec = min(duration_sec, start_sec + max(window_before_sec, window_after_sec, 0.1))
    segment_id = str(segment["segment_id"])
    prefix = "motion" if candidate_type == "event_candidate" else "stable_negative"
    peak_motion_score = motion_summary.get("peak_motion_score")
    peak_motion_score_output_zone = motion_summary.get("peak_motion_score_output_zone")
    return {
        "station_id": station_id,
        "candidate_id": f"{segment_id}_{prefix}_{index:04d}",
        "window_id": f"{segment_id}_{prefix}_{index:04d}",
        "segment_id": segment_id,
        "segment_path": segment["path"],
        "candidate_type": candidate_type,
        "proposal_type": proposal_type,
        "candidate_reasons": candidate_reasons,
        "start_offset_sec": round(start_sec, 3),
        "end_offset_sec": round(end_sec, 3),
        "center_offset_sec": round(center_sec, 3),
        "duration_sec": round(end_sec - start_sec, 3),
        "source_start_wall_ts": segment.get("start_wall_ts"),
        "source_end_wall_ts": segment.get("end_wall_ts"),
        "label_status": "unreviewed",
        "label_authority_tier": "bronze",
        "evidence_role": "candidate_only_not_truth",
        "validation_truth_eligible": False,
        "training_eligible": False,
        "generated_by": GENERATED_BY,
        "peak_motion_score": peak_motion_score,
        "peak_motion_score_output_zone": peak_motion_score_output_zone,
        "teacher_task": "verify_candidate_event",
        "teacher_questions": [
            "Compare the stable before and after evidence. Did the output stack gain one countable finished part?",
            "If yes, what timestamp best represents the completed placement?",
            "Is this worker-only, static-stack, in-transit, duplicate, completed, or unclear?",
        ],
        "required_evidence_packet_assets": [
            "event_clip",
            "before_full_frame",
            "during_full_frame",
            "after_full_frame",
            "output_zone_crop_sequence",
            "stack_crop_sequence",
            "frame_diff_or_motion_heatmap",
        ],
        "motion_summary": motion_summary,
    }


def _stable_negative_proposals(
    *,
    station_id: str,
    segment: dict[str, Any],
    samples: list[dict[str, Any]],
    occupied_windows: list[tuple[float, float]],
    count: int,
    duration_sec: float,
    window_before_sec: float,
    window_after_sec: float,
    stable_threshold: float,
    score_key: str,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    stable_samples = [
        sample
        for sample in samples
        if float(sample.get(score_key) or 0.0) <= stable_threshold
        and not _timestamp_in_windows(float(sample["timestamp_sec"]), occupied_windows)
    ]
    if not stable_samples:
        return []
    selected = _spread_samples(stable_samples, count=count)
    proposals: list[dict[str, Any]] = []
    for index, sample in enumerate(selected, start=1):
        proposals.append(
            _build_proposal(
                station_id=station_id,
                segment=segment,
                index=index,
                candidate_type="hard_negative_candidate",
                proposal_type="stable_hard_negative",
                center_sec=float(sample["timestamp_sec"]),
                duration_sec=duration_sec,
                window_before_sec=window_before_sec,
                window_after_sec=window_after_sec,
                candidate_reasons=["low_motion_stable_sample"],
                motion_summary={
                    "peak_motion_score": round(float(sample["motion_score"]), 6),
                    "peak_motion_score_output_zone": _rounded_optional(sample.get("motion_score_output_zone")),
                    "stable_before_sec": round(float(sample["timestamp_sec"]), 3),
                    "stable_after_sec": round(float(sample["timestamp_sec"]), 3),
                },
            )
        )
    return proposals


def _timestamp_in_windows(timestamp_sec: float, windows: list[tuple[float, float]]) -> bool:
    return any(start_sec <= timestamp_sec <= end_sec for start_sec, end_sec in windows)


def _spread_samples(samples: list[dict[str, Any]], *, count: int) -> list[dict[str, Any]]:
    if len(samples) <= count:
        return samples
    if count == 1:
        return [samples[len(samples) // 2]]
    last_index = len(samples) - 1
    selected: list[dict[str, Any]] = []
    for index in range(count):
        selected_index = round(index * last_index / (count - 1))
        selected.append(samples[selected_index])
    return selected


def _nearest_stable_timestamp(
    *,
    samples: list[dict[str, Any]],
    center_sec: float,
    direction: str,
    stable_threshold: float,
    score_key: str = "motion_score",
) -> float | None:
    if direction == "before":
        candidates = [sample for sample in samples if float(sample["timestamp_sec"]) < center_sec]
        candidates.reverse()
    elif direction == "after":
        candidates = [sample for sample in samples if float(sample["timestamp_sec"]) > center_sec]
    else:
        raise ValueError("direction must be before or after")
    for sample in candidates:
        if float(sample.get(score_key) or 0.0) <= stable_threshold:
            return round(float(sample["timestamp_sec"]), 3)
    return None


def _score_key_for_mode(proposal_mode: str) -> str:
    if proposal_mode == "full_frame_motion":
        return "motion_score"
    if proposal_mode == "output_zone_motion":
        return "motion_score_output_zone"
    raise ValueError(f"unsupported proposal_mode: {proposal_mode}")


def _build_polygon_mask(*, cv2: Any, frame_shape: tuple[int, int], polygon: list[list[float]]) -> Any:
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError("zone motion proposal requires numpy; use the repo .venv") from exc
    height, width = frame_shape[:2]
    points = []
    for x_norm, y_norm in polygon:
        x = min(width - 1, max(0, int(round(float(x_norm) * float(width - 1)))))
        y = min(height - 1, max(0, int(round(float(y_norm) * float(height - 1)))))
        points.append([x, y])
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(points, dtype=np.int32)], 255)
    return mask


def _validate_polygon(polygon: list[list[float]], *, name: str) -> None:
    if len(polygon) < 3:
        raise ValueError(f"{name} must contain at least 3 points")
    for index, point in enumerate(polygon):
        if len(point) != 2:
            raise ValueError(f"{name}[{index}] must be [x, y]")
        float(point[0])
        float(point[1])


def _rounded_optional(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)
