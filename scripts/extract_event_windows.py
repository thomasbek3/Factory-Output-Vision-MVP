#!/usr/bin/env python3
"""Extract deterministic active-learning event evidence windows from app artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "factory-vision-event-evidence-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVACY_MODES = ("offline_local", "cloud_assisted_setup", "cloud_assisted_audit")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("._-") or "item"


def resolve_manifest_path(*, case_id: str | None, manifest_path: Path | None, registry_path: Path) -> Path | None:
    if manifest_path is not None:
        return manifest_path
    if not case_id:
        return None
    registry = read_json(registry_path)
    for entry in registry.get("cases") or []:
        if entry.get("case_id") == case_id:
            return Path(entry["manifest_path"])
    raise KeyError(f"case_id not found in {registry_path}: {case_id}")


def _fps_from_manifest(manifest: dict[str, Any] | None) -> float | None:
    runtime = (manifest or {}).get("runtime") or {}
    for key in ("reader_fps", "processing_fps"):
        value = runtime.get(key)
        if value:
            return float(value)
    return None


def _frame_index_for_ts(ts_sec: float, fps: float | None) -> int | None:
    if fps is None or fps <= 0:
        return None
    return max(0, int(round(ts_sec * fps)))


def _event_center_frame(event: dict[str, Any], center_sec: float, fps: float | None) -> int | None:
    raw = event.get("reader_frame_sequence_index")
    if raw is not None:
        return int(raw)
    return _frame_index_for_ts(center_sec, fps)


def _time_window(center_sec: float, before_sec: float, after_sec: float, duration_sec: float | None) -> dict[str, float]:
    start_sec = max(0.0, center_sec - before_sec)
    end_sec = center_sec + after_sec
    if duration_sec is not None:
        end_sec = min(float(duration_sec), end_sec)
    return {
        "start_sec": round(start_sec, 3),
        "end_sec": round(max(start_sec, end_sec), 3),
        "center_sec": round(center_sec, 3),
    }


def _frame_window(
    *,
    event: dict[str, Any],
    time_window: dict[str, float],
    fps: float | None,
) -> dict[str, Any]:
    center_frame = _event_center_frame(event, float(time_window["center_sec"]), fps)
    return {
        "start_frame_index": _frame_index_for_ts(float(time_window["start_sec"]), fps),
        "end_frame_index": _frame_index_for_ts(float(time_window["end_sec"]), fps),
        "center_frame_index": center_frame,
        "frame_index_basis": "reader_frame_sequence_index_or_timestamp_estimate",
    }


def _risk_from_event(event: dict[str, Any]) -> dict[str, str]:
    authority = str(event.get("count_authority") or "")
    reason = str(event.get("reason") or "")
    duplicate_risk = "unknown"
    miss_risk = "unknown"
    confidence_tier = "unknown"
    if authority == "source_token_authorized":
        confidence_tier = "medium"
    if "end_of_stream" in reason:
        miss_risk = "medium"
    if str(event.get("provenance_status") or "") == "synthetic_approved_chain_token":
        confidence_tier = "low"
        duplicate_risk = "medium"
    return {
        "confidence_tier": confidence_tier,
        "duplicate_risk": duplicate_risk,
        "miss_risk": miss_risk,
    }


def _review_window_metadata(window: dict[str, Any]) -> dict[str, Any]:
    time_window = window["time_window"]
    return {
        "window_id": window["window_id"],
        "start_sec": time_window["start_sec"],
        "end_sec": time_window["end_sec"],
        "review_status": "not_reviewed",
    }


def read_video_frame_at_timestamp(video_path: Path, timestamp_sec: float) -> Any:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("review-frame extraction requires cv2; use the repo .venv") from exc

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video for frame extraction: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(timestamp_sec)) * 1000.0)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s from {video_path}")
    return frame


def write_cv2_frame(path: Path, frame: Any) -> None:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("review-frame extraction requires cv2; use the repo .venv") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"could not write review frame: {path}")


def resize_frame_to_max_width(frame: Any, max_width: int | None) -> Any:
    if max_width is None or max_width <= 0 or not hasattr(frame, "shape"):
        return frame
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("review-frame resizing requires cv2; use the repo .venv") from exc
    scale = max_width / float(width)
    return cv2.resize(frame, (max_width, max(1, int(round(height * scale)))), interpolation=cv2.INTER_AREA)


def write_review_frames_for_evidence(
    *,
    evidence: dict[str, Any],
    video_path: Path,
    frame_output_dir: Path,
    force: bool,
    max_width: int | None = 960,
    frame_reader: Callable[[Path, float], Any] = read_video_frame_at_timestamp,
    frame_writer: Callable[[Path, Any], None] = write_cv2_frame,
) -> dict[str, Any]:
    updated = dict(evidence)
    updated_windows: list[dict[str, Any]] = []
    for window in evidence.get("windows") or []:
        updated_window = dict(window)
        review_window = dict(updated_window.get("review_window") or {})
        sample_timestamps = [float(value) for value in review_window.get("sample_timestamps_sec") or []]
        assets: list[dict[str, Any]] = []
        window_dir = frame_output_dir / safe_path_part(str(updated_window["window_id"]))
        for index, timestamp_sec in enumerate(sample_timestamps):
            frame_path = window_dir / f"frame_{index:02d}_{timestamp_sec:.3f}s.jpg"
            if frame_path.exists() and not force:
                raise FileExistsError(frame_path)
            frame = frame_reader(video_path, timestamp_sec)
            frame = resize_frame_to_max_width(frame, max_width)
            frame_writer(frame_path, frame)
            assets.append(
                {
                    "timestamp_sec": round(timestamp_sec, 3),
                    "frame_path": frame_path.as_posix(),
                    "sha256": sha256_file(frame_path),
                    "status": "written",
                }
            )
        review_window["asset_status"] = "frames_extracted"
        review_window["frame_assets"] = assets
        updated_window["review_window"] = review_window
        updated_windows.append(updated_window)
    updated["windows"] = updated_windows
    return updated


def build_count_event_window(
    *,
    case_id: str,
    event: dict[str, Any],
    event_index: int,
    before_sec: float,
    after_sec: float,
    duration_sec: float | None,
    fps: float | None,
) -> dict[str, Any]:
    center_sec = float(event["event_ts"])
    time_window = _time_window(center_sec, before_sec, after_sec, duration_sec)
    risk = _risk_from_event(event)
    sample_timestamps = [
        time_window["start_sec"],
        time_window["center_sec"],
        time_window["end_sec"],
    ]
    return {
        "window_id": f"{case_id}-count-{event_index + 1:04d}",
        "window_type": "count_event",
        "event_index": event_index,
        "time_window": time_window,
        "frame_window": _frame_window(event=event, time_window=time_window, fps=fps),
        "count_event_evidence": event,
        "review_window": {
            "sample_timestamps_sec": sample_timestamps,
            "asset_status": "metadata_only",
            "review_question": "Did this ordered window contain one distinct completed placement under the case truth rule?",
        },
        "label_authority_tier": "bronze",
        "notes": ["Runtime count evidence only; not validation truth."],
        **risk,
    }


def _overlaps(center_sec: float, half_width_sec: float, occupied: list[tuple[float, float]]) -> bool:
    start = center_sec - half_width_sec
    end = center_sec + half_width_sec
    return any(start <= occupied_end and end >= occupied_start for occupied_start, occupied_end in occupied)


def build_negative_windows(
    *,
    case_id: str,
    count_windows: list[dict[str, Any]],
    duration_sec: float | None,
    fps: float | None,
    count: int,
    window_sec: float,
) -> list[dict[str, Any]]:
    if count <= 0 or duration_sec is None or duration_sec <= 0:
        return []
    occupied = [
        (float(window["time_window"]["start_sec"]), float(window["time_window"]["end_sec"]))
        for window in count_windows
    ]
    half_width = max(0.1, window_sec / 2.0)
    step = max(window_sec, float(duration_sec) / max(2, count * 4))
    center = half_width
    windows: list[dict[str, Any]] = []
    while center < float(duration_sec) and len(windows) < count:
        if not _overlaps(center, half_width, occupied):
            time_window = _time_window(center, half_width, half_width, duration_sec)
            empty_event: dict[str, Any] = {}
            index = len(windows) + 1
            windows.append(
                {
                    "window_id": f"{case_id}-negative-{index:04d}",
                    "window_type": "negative_background",
                    "event_index": None,
                    "time_window": time_window,
                    "frame_window": _frame_window(event=empty_event, time_window=time_window, fps=fps),
                    "count_event_evidence": None,
                    "review_window": {
                        "sample_timestamps_sec": [
                            time_window["start_sec"],
                            time_window["center_sec"],
                            time_window["end_sec"],
                        ],
                        "asset_status": "metadata_only",
                        "review_question": "Does this background window contain no countable completed placement?",
                    },
                    "confidence_tier": "unknown",
                    "duplicate_risk": "low",
                    "miss_risk": "unknown",
                    "label_authority_tier": "bronze",
                    "notes": ["Deterministic negative/background candidate; review before training."],
                }
            )
        center += step
    return windows


def build_event_evidence(
    *,
    case_id: str | None,
    manifest_path: Path | None,
    observed_events_path: Path,
    video_path: Path | None,
    video_sha256: str | None,
    privacy_mode: str,
    window_before_sec: float,
    window_after_sec: float,
    include_negatives: bool,
    negative_count: int,
    negative_window_sec: float,
    frame_output_dir: Path | None = None,
    force_frame_output: bool = False,
    review_frame_max_width: int | None = 960,
) -> dict[str, Any]:
    manifest = read_json(manifest_path) if manifest_path is not None else None
    observed = read_json(observed_events_path)
    resolved_case_id = case_id or (manifest or {}).get("case_id") or "ad_hoc"
    video = (manifest or {}).get("video") or {}
    raw_video_path = str(video.get("path") or "")
    resolved_video_path = video_path or (Path(raw_video_path) if raw_video_path else None)
    resolved_video_sha256 = video_sha256 or video.get("sha256")
    if not resolved_video_sha256 and resolved_video_path is not None and resolved_video_path.exists() and resolved_video_path.is_file():
        resolved_video_sha256 = sha256_file(resolved_video_path)
    duration_sec = video.get("duration_sec") or observed.get("observed_coverage_end_sec")
    fps = _fps_from_manifest(manifest)

    count_windows = [
        build_count_event_window(
            case_id=resolved_case_id,
            event=event,
            event_index=index,
            before_sec=window_before_sec,
            after_sec=window_after_sec,
            duration_sec=float(duration_sec) if duration_sec is not None else None,
            fps=fps,
        )
        for index, event in enumerate(observed.get("events") or [])
        if event.get("event_ts") is not None
    ]
    negative_windows = (
        build_negative_windows(
            case_id=resolved_case_id,
            count_windows=count_windows,
            duration_sec=float(duration_sec) if duration_sec is not None else None,
            fps=fps,
            count=negative_count,
            window_sec=negative_window_sec,
        )
        if include_negatives
        else []
    )
    windows = count_windows + negative_windows
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "case_id": resolved_case_id,
        "privacy_mode": privacy_mode,
        "video": {
            "path": resolved_video_path.as_posix() if resolved_video_path is not None else "",
            "sha256": resolved_video_sha256 or "",
            "duration_sec": duration_sec,
            "width": video.get("width"),
            "height": video.get("height"),
            "codec": video.get("codec"),
        },
        "source_artifacts": {
            "manifest_path": manifest_path.as_posix() if manifest_path is not None else None,
            "observed_events_path": observed_events_path.as_posix(),
            "truth_ledger_path": ((manifest or {}).get("truth") or {}).get("truth_ledger_path"),
            "comparison_report_path": ((manifest or {}).get("proof_artifacts") or {}).get("comparison_report"),
        },
        "model_settings": dict((manifest or {}).get("runtime") or {}),
        "windows": windows,
        "review_window_metadata": [_review_window_metadata(window) for window in windows],
    }
    if frame_output_dir is not None:
        if resolved_video_path is None:
            raise ValueError("review-frame extraction requires a video path")
        evidence = write_review_frames_for_evidence(
            evidence=evidence,
            video_path=resolved_video_path,
            frame_output_dir=frame_output_dir,
            force=force_frame_output,
            max_width=review_frame_max_width,
        )
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract active-learning event evidence windows")
    parser.add_argument("--case-id")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path, default=Path("validation/registry.json"))
    parser.add_argument("--observed-events", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--video-sha256")
    parser.add_argument("--privacy-mode", choices=PRIVACY_MODES, default="offline_local")
    parser.add_argument("--window-before-sec", type=float, default=2.0)
    parser.add_argument("--window-after-sec", type=float, default=2.0)
    parser.add_argument("--include-negatives", action="store_true")
    parser.add_argument("--negative-count", type=int, default=0)
    parser.add_argument("--negative-window-sec", type=float, default=2.0)
    parser.add_argument("--extract-review-frames", action="store_true")
    parser.add_argument("--frame-output-dir", type=Path)
    parser.add_argument("--review-frame-max-width", type=int, default=960)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = resolve_manifest_path(
        case_id=args.case_id,
        manifest_path=args.manifest,
        registry_path=args.registry,
    )
    manifest = read_json(manifest_path) if manifest_path is not None else None
    observed_events_path = args.observed_events
    if observed_events_path is None and manifest is not None:
        observed_events_path = Path(manifest["proof_artifacts"]["observed_events"])
    if observed_events_path is None:
        raise ValueError("either --case-id/--manifest with observed artifacts or --observed-events is required")

    frame_output_dir = args.frame_output_dir
    if args.extract_review_frames and frame_output_dir is None:
        case_part = args.case_id or (manifest or {}).get("case_id") or "ad_hoc"
        frame_output_dir = Path("data/reports/active_learning/review_frames") / safe_path_part(str(case_part))

    payload = build_event_evidence(
        case_id=args.case_id,
        manifest_path=manifest_path,
        observed_events_path=observed_events_path,
        video_path=args.video,
        video_sha256=args.video_sha256,
        privacy_mode=args.privacy_mode,
        window_before_sec=args.window_before_sec,
        window_after_sec=args.window_after_sec,
        include_negatives=args.include_negatives,
        negative_count=args.negative_count,
        negative_window_sec=args.negative_window_sec,
        frame_output_dir=frame_output_dir if args.extract_review_frames else None,
        force_frame_output=args.force,
        review_frame_max_width=args.review_frame_max_width,
    )
    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": args.output.as_posix(), "window_count": len(payload["windows"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
