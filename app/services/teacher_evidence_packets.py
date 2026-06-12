from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.services.stream_recorder import sha256_file


SCHEMA_VERSION = "factory-vision-teacher-evidence-packets-v2"
GENERATED_BY = "teacher_evidence_packet_renderer_v2"


def build_teacher_evidence_packets(
    *,
    event_proposals_path: Path,
    output_dir: Path,
    sequence_fps: float = 2.0,
    max_packets: int | None = None,
    max_width: int = 960,
    output_zone_polygon: list[list[float]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if sequence_fps <= 0:
        raise ValueError("sequence_fps must be positive")
    if max_packets is not None and max_packets <= 0:
        raise ValueError("max_packets must be positive when provided")
    if max_width <= 0:
        raise ValueError("max_width must be positive")
    proposals_payload = json.loads(event_proposals_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    packets: list[dict[str, Any]] = []
    proposals = list(proposals_payload.get("proposals") or [])
    if max_packets is not None:
        proposals = proposals[:max_packets]
    for proposal in proposals:
        packet = build_teacher_evidence_packet(
            proposal=proposal,
            output_root=output_dir,
            sequence_fps=sequence_fps,
            max_width=max_width,
            output_zone_polygon=output_zone_polygon,
            force=force,
        )
        packets.append(packet)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "station_id": proposals_payload.get("station_id"),
        "source_event_proposals_path": str(event_proposals_path),
        "source_event_proposals_schema_version": proposals_payload.get("schema_version"),
        "generated_by": GENERATED_BY,
        "privacy_mode": proposals_payload.get("privacy_mode", "offline_local"),
        "refuses_validation_truth": True,
        "sequence_fps": float(sequence_fps),
        "packet_count": len(packets),
        "packets": packets,
    }
    manifest_path = output_dir / "teacher_evidence_manifest.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(manifest_path)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_teacher_evidence_packet(
    *,
    proposal: dict[str, Any],
    output_root: Path,
    sequence_fps: float,
    max_width: int,
    output_zone_polygon: list[list[float]] | None,
    force: bool,
) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("teacher evidence packet rendering requires cv2; use the repo .venv") from exc
    candidate_id = safe_path_part(str(proposal["candidate_id"]))
    packet_dir = output_root / candidate_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    segment_path = Path(str(proposal["segment_path"]))
    start_sec = float(proposal["start_offset_sec"])
    center_sec = float(proposal["center_offset_sec"])
    end_sec = float(proposal["end_offset_sec"])
    before_sec = _preferred_timestamp(proposal, "stable_before_sec", fallback=start_sec)
    after_sec = _preferred_timestamp(proposal, "stable_after_sec", fallback=end_sec)

    # Windows near a segment edge can extend past the last decodable frame; clamp into range.
    max_readable_sec = _max_readable_timestamp_sec(cv2=cv2, video_path=segment_path)
    if max_readable_sec is not None:
        start_sec = min(max(start_sec, 0.0), max_readable_sec)
        center_sec = min(max(center_sec, 0.0), max_readable_sec)
        end_sec = min(max(end_sec, 0.0), max_readable_sec)
        before_sec = min(max(before_sec, 0.0), max_readable_sec)
        after_sec = min(max(after_sec, 0.0), max_readable_sec)

    clip_path = packet_dir / "event_clip.mp4"
    _extract_clip(
        source=segment_path,
        output=clip_path,
        start_sec=start_sec,
        end_sec=end_sec,
        force=force,
    )

    before_frame, before_sec = _read_frame_with_backoff(cv2=cv2, video_path=segment_path, timestamp_sec=before_sec)
    during_frame, center_sec = _read_frame_with_backoff(cv2=cv2, video_path=segment_path, timestamp_sec=center_sec)
    after_frame, after_sec = _read_frame_with_backoff(cv2=cv2, video_path=segment_path, timestamp_sec=after_sec)
    before_path = packet_dir / "before_full.jpg"
    during_path = packet_dir / "during_full.jpg"
    after_path = packet_dir / "after_full.jpg"
    _write_frame(cv2=cv2, path=before_path, frame=_resize_to_width(cv2=cv2, frame=before_frame, max_width=max_width), force=force)
    _write_frame(cv2=cv2, path=during_path, frame=_resize_to_width(cv2=cv2, frame=during_frame, max_width=max_width), force=force)
    _write_frame(cv2=cv2, path=after_path, frame=_resize_to_width(cv2=cv2, frame=after_frame, max_width=max_width), force=force)

    diff_path = packet_dir / "before_after_diff_heatmap.jpg"
    diff_frame = _diff_heatmap(cv2=cv2, before=before_frame, after=after_frame)
    _write_frame(cv2=cv2, path=diff_path, frame=_resize_to_width(cv2=cv2, frame=diff_frame, max_width=max_width), force=force)

    sequence_assets = _write_sequence_assets(
        cv2=cv2,
        video_path=segment_path,
        packet_dir=packet_dir,
        start_sec=start_sec,
        end_sec=end_sec,
        sequence_fps=sequence_fps,
        max_width=max_width,
        output_zone_polygon=output_zone_polygon,
        force=force,
    )
    assets = [
        _asset(kind="event_clip", path=clip_path, timestamp_sec=None),
        _asset(kind="before_full_frame", path=before_path, timestamp_sec=before_sec),
        _asset(kind="during_full_frame", path=during_path, timestamp_sec=center_sec),
        _asset(kind="after_full_frame", path=after_path, timestamp_sec=after_sec),
        _asset(kind="frame_diff_or_motion_heatmap", path=diff_path, timestamp_sec=None),
        *sequence_assets,
    ]
    packet_manifest = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": candidate_id,
        "candidate_id": proposal["candidate_id"],
        "window_id": proposal.get("window_id"),
        "station_id": proposal.get("station_id"),
        "segment_id": proposal.get("segment_id"),
        "segment_path": proposal.get("segment_path"),
        "candidate_type": proposal.get("candidate_type"),
        "proposal_type": proposal.get("proposal_type"),
        "window": {
            "start_offset_sec": start_sec,
            "center_offset_sec": center_sec,
            "end_offset_sec": end_sec,
            "before_sec": before_sec,
            "after_sec": after_sec,
        },
        "source_proposal": proposal,
        "teacher_task": "verify_candidate_event",
        "teacher_prompt_contract": {
            "question": "Did this bounded evidence packet show one completed countable output placement?",
            "required_outputs": [
                "teacher_output_status",
                "suggested_event_ts_sec",
                "confidence_tier",
                "duplicate_risk",
                "miss_risk",
                "rationale",
            ],
            "allowed_statuses": ["completed", "in_transit", "static_stack", "worker_only", "unclear"],
            "instruction": "Use the before/during/after frames, sequence crops, and diff heatmap. Do not infer validation truth.",
        },
        "crop_source": "station_calibration_output_zone" if output_zone_polygon is not None else "full_frame_fallback",
        "assets": assets,
        "label_authority_tier": "bronze",
        "evidence_role": "candidate_only_not_truth",
        "validation_truth_eligible": False,
        "training_eligible": False,
        "generated_by": GENERATED_BY,
    }
    packet_manifest_path = packet_dir / "packet_manifest.json"
    if packet_manifest_path.exists() and not force:
        raise FileExistsError(packet_manifest_path)
    packet_manifest_path.write_text(json.dumps(packet_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "packet_id": candidate_id,
        "candidate_id": proposal["candidate_id"],
        "packet_manifest_path": str(packet_manifest_path),
        "packet_dir": str(packet_dir),
        "asset_count": len(assets),
        "candidate_type": proposal.get("candidate_type"),
        "proposal_type": proposal.get("proposal_type"),
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


def safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("._-") or "packet"


def write_teacher_evidence_manifest(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _preferred_timestamp(proposal: dict[str, Any], key: str, *, fallback: float) -> float:
    value = (proposal.get("motion_summary") or {}).get(key)
    if value is None:
        return fallback
    return float(value)


def _extract_clip(*, source: Path, output: Path, start_sec: float, end_sec: float, force: bool) -> None:
    if output.exists() and not force:
        raise FileExistsError(output)
    if not source.exists():
        raise FileNotFoundError(source)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to render teacher event clips")
    duration_sec = max(0.1, end_sec - start_sec)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration_sec:.3f}",
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=max(30.0, duration_sec * 10.0))


def _max_readable_timestamp_sec(*, cv2: Any, video_path: Path) -> float | None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None
    try:
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        capture.release()
    if frame_count <= 0.0 or fps <= 0.0:
        return None
    # Keep a two-frame margin: seeking to the very last frame of an MKV segment is unreliable.
    return max(0.0, (frame_count - 2.0) / fps)


def _read_frame_with_backoff(
    *,
    cv2: Any,
    video_path: Path,
    timestamp_sec: float,
    backoffs_sec: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0),
) -> tuple[Any, float]:
    """Read a frame, walking earlier when container metadata over-reports the readable range."""
    last_error: Exception | None = None
    for backoff in backoffs_sec:
        candidate_sec = max(0.0, timestamp_sec - backoff)
        try:
            return _read_frame(cv2=cv2, video_path=video_path, timestamp_sec=candidate_sec), candidate_sec
        except RuntimeError as exc:
            last_error = exc
            if candidate_sec == 0.0:
                break
    raise RuntimeError(f"could not read any frame near {timestamp_sec:.3f}s from {video_path}") from last_error


def _read_frame(*, cv2: Any, video_path: Path, timestamp_sec: float) -> Any:
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


def _write_frame(*, cv2: Any, path: Path, frame: Any, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"could not write frame: {path}")


def _resize_to_width(*, cv2: Any, frame: Any, max_width: int) -> Any:
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    scale = max_width / float(width)
    return cv2.resize(frame, (max_width, max(1, int(round(height * scale)))), interpolation=cv2.INTER_AREA)


def _diff_heatmap(*, cv2: Any, before: Any, after: Any) -> Any:
    if before.shape[:2] != after.shape[:2]:
        after = cv2.resize(after, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_AREA)
    diff = cv2.absdiff(before, after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    return cv2.applyColorMap(gray, cv2.COLORMAP_JET)


def _write_sequence_assets(
    *,
    cv2: Any,
    video_path: Path,
    packet_dir: Path,
    start_sec: float,
    end_sec: float,
    sequence_fps: float,
    max_width: int,
    output_zone_polygon: list[list[float]] | None,
    force: bool,
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    timestamps = _sequence_timestamps(start_sec=start_sec, end_sec=end_sec, fps=sequence_fps)
    kinds = ("output_zone_crop_sequence",) if output_zone_polygon is not None else ("output_zone_crop_sequence", "stack_crop_sequence")
    for kind in kinds:
        sequence_dir = packet_dir / kind
        for index, timestamp_sec in enumerate(timestamps):
            try:
                frame = _read_frame(cv2=cv2, video_path=video_path, timestamp_sec=timestamp_sec)
            except RuntimeError:
                # Trailing timestamps can sit past the last decodable frame of a segment; skip them.
                continue
            if output_zone_polygon is not None:
                frame = _crop_polygon_bbox_with_margin(cv2=cv2, frame=frame, polygon=output_zone_polygon)
                frame = _resize_to_width(cv2=cv2, frame=frame, max_width=max(max_width, 768))
            else:
                frame = _resize_to_width(cv2=cv2, frame=frame, max_width=max_width)
            frame_path = sequence_dir / f"frame_{index:03d}_{timestamp_sec:.3f}s.jpg"
            _write_frame(cv2=cv2, path=frame_path, frame=frame, force=force)
            assets.append(_asset(kind=kind, path=frame_path, timestamp_sec=timestamp_sec))
    return assets


def _crop_polygon_bbox_with_margin(*, cv2: Any, frame: Any, polygon: list[list[float]], margin_fraction: float = 0.10) -> Any:
    height, width = frame.shape[:2]
    xs = [float(point[0]) * float(width - 1) for point in polygon]
    ys = [float(point[1]) * float(height - 1) for point in polygon]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    margin_x = (max_x - min_x) * margin_fraction
    margin_y = (max_y - min_y) * margin_fraction
    left = max(0, int(round(min_x - margin_x)))
    right = min(width, int(round(max_x + margin_x)) + 1)
    top = max(0, int(round(min_y - margin_y)))
    bottom = min(height, int(round(max_y + margin_y)) + 1)
    if right <= left or bottom <= top:
        raise ValueError("output_zone_polygon produced an empty crop")
    return frame[top:bottom, left:right]


def _sequence_timestamps(*, start_sec: float, end_sec: float, fps: float) -> list[float]:
    if end_sec <= start_sec:
        return [round(start_sec, 3)]
    step = 1.0 / fps
    timestamps: list[float] = []
    current = start_sec
    while current <= end_sec:
        timestamps.append(round(current, 3))
        current += step
    if timestamps[-1] < round(end_sec, 3):
        timestamps.append(round(end_sec, 3))
    return timestamps


def _asset(*, kind: str, path: Path, timestamp_sec: float | None) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "timestamp_sec": round(timestamp_sec, 3) if timestamp_sec is not None else None,
        "sha256": sha256_file(path),
    }
