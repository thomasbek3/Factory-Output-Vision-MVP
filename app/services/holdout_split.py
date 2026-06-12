from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.services.stream_recorder import sha256_file

LEDGER_SCHEMA_VERSION = "derived-holdout-human-truth-ledger-v1"
CASE_SCHEMA_VERSION = "factory-vision-video-manifest-v1"
GENERATED_BY = "holdout_split_v1"

# Fixed across all auto-onboarded stations. A station failing the gate with these params is a
# finding about the pipeline, not something to fix with per-station hand-tuning.
STANDARD_EVENT_PARAMS: dict[str, Any] = {
    "demo_count_mode": "live_reader_snapshot",
    "counting_mode": "event_based",
    "processing_fps": 10.0,
    "reader_fps": 10.0,
    "runtime_calibration_path": None,
    "yolo_confidence": 0.25,
    "event_track_max_age": 30,
    "event_track_min_frames": 8,
    "event_detection_cluster_distance": 150.0,
    "event_track_min_travel_px": None,
    "event_count_debounce_sec": None,
    "event_track_max_match_distance": None,
}

EVENT_SPLIT_MARGIN_SEC = 5.0


def probe_keyframes(video_path: Path, *, timeout_sec: float = 600.0) -> list[float]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=pts_time,flags",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=True,
    )
    keyframes: list[float] = []
    for line in completed.stdout.splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 2 and "K" in parts[1] and parts[0] not in {"", "N/A"}:
            keyframes.append(float(parts[0]))
    return sorted(set(keyframes))


def probe_video(video_path: Path, *, timeout_sec: float = 120.0) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=True,
    )
    payload = json.loads(completed.stdout)
    stream = (payload.get("streams") or [{}])[0]
    duration = stream.get("duration") or (payload.get("format") or {}).get("duration")
    return {
        "path": str(video_path),
        "duration_sec": float(duration) if duration else None,
        "width": int(stream["width"]) if stream.get("width") else None,
        "height": int(stream["height"]) if stream.get("height") else None,
        "codec": stream.get("codec_name"),
    }


def compute_holdout_split(
    *,
    duration_sec: float,
    truth_event_timestamps: list[float],
    keyframes: list[float],
    train_fraction: float = 0.7,
    min_holdout_truth_events: int = 3,
) -> dict[str, Any]:
    """Pick a keyframe-aligned split that leaves enough truth events in the holdout tail."""
    events = sorted(float(value) for value in truth_event_timestamps)
    requested = duration_sec * train_fraction
    split = _latest_keyframe_at_or_before(keyframes, requested)
    adjusted = False

    if len(events) >= min_holdout_truth_events:
        guaranteeing_event = events[len(events) - min_holdout_truth_events]
        if split > guaranteeing_event - EVENT_SPLIT_MARGIN_SEC:
            split = _latest_keyframe_at_or_before(keyframes, guaranteeing_event - EVENT_SPLIT_MARGIN_SEC)
            adjusted = True

    # Never split through the middle of an event window.
    for event_ts in events:
        if abs(event_ts - split) < EVENT_SPLIT_MARGIN_SEC and split > 0.0:
            split = _latest_keyframe_at_or_before(keyframes, event_ts - EVENT_SPLIT_MARGIN_SEC)
            adjusted = True

    holdout_events = [event_ts for event_ts in events if event_ts >= split]
    return {
        "requested_split_sec": round(requested, 3),
        "split_sec": round(split, 3),
        "train_fraction": train_fraction,
        "min_holdout_truth_events": min_holdout_truth_events,
        "holdout_truth_event_count": len(holdout_events),
        "train_truth_event_count": len(events) - len(holdout_events),
        "adjusted": adjusted,
    }


def cut_clips(
    *,
    video_path: Path,
    split_sec: float,
    train_clip_path: Path,
    holdout_clip_path: Path,
    force: bool = False,
    timeout_sec: float = 1800.0,
) -> dict[str, Any]:
    for output in (train_clip_path, holdout_clip_path):
        if output.exists() and not force:
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-t", f"{split_sec:.3f}", "-c", "copy", str(train_clip_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=True,
    )
    # split_sec is a probed keyframe, so -ss before -i with stream copy starts exactly there.
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{split_sec:.3f}", "-i", str(video_path), "-c", "copy", str(holdout_clip_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=True,
    )
    return {
        "method": "stream_copy_keyframe_aligned",
        "split_sec": round(split_sec, 3),
        "train_clip": probe_video(train_clip_path),
        "holdout_clip": probe_video(holdout_clip_path),
    }


def derive_holdout_truth_ledger(
    *,
    source_ledger_path: Path,
    split_sec: float,
    output_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    source = json.loads(source_ledger_path.read_text(encoding="utf-8"))
    holdout_events = []
    for event in sorted(source.get("events") or [], key=lambda row: float(row.get("event_ts") or 0.0)):
        event_ts = float(event.get("event_ts") or 0.0)
        if event_ts < split_sec:
            continue
        holdout_events.append(
            {
                "truth_event_id": f"holdout-{event.get('truth_event_id')}",
                "source_truth_event_id": event.get("truth_event_id"),
                "event_ts": round(event_ts - split_sec, 3),
                "source_event_ts": event_ts,
                "count_total": len(holdout_events) + 1,
            }
        )
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "source_truth_ledger_path": str(source_ledger_path),
        "source_truth_ledger_sha256": sha256_file(source_ledger_path),
        "source_schema_version": source.get("schema_version"),
        "split_sec": round(split_sec, 3),
        "counting_rule": source.get("counting_rule") or source.get("count_rule"),
        "expected_human_total": len(holdout_events),
        "events": holdout_events,
    }
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def author_holdout_case_manifest(
    *,
    station_id: str,
    holdout_clip_path: Path,
    derived_ledger: dict[str, Any],
    derived_ledger_path: Path,
    model_path: Path,
    playback_speed: float,
    runtime_calibration_path: Path | None = None,
    backend_port: int = 8093,
    frontend_port: int = 5175,
    output_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    video = probe_video(holdout_clip_path)
    video["sha256"] = sha256_file(holdout_clip_path)
    expected_total = int(derived_ledger["expected_human_total"])
    runtime = dict(STANDARD_EVENT_PARAMS)
    runtime["playback_speed"] = float(playback_speed)
    runtime["model_path"] = str(model_path)
    if runtime_calibration_path is not None:
        # Auto-derived zones (landing-box union + busiest-motion source) — still zero human input.
        runtime["runtime_calibration_path"] = str(runtime_calibration_path)
    manifest = {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": f"{station_id}_auto_holdout",
        "display_name": f"{station_id} autonomous-onboarding holdout (derived)",
        "status": "derived_rehearsal_holdout",
        "promotion_status": "not_promoted",
        "verified_at": None,
        "video": video,
        "truth": {
            "rule_id": f"derived_holdout_{expected_total}",
            "expected_total": expected_total,
            "count_rule": derived_ledger.get("counting_rule"),
            "truth_ledger_path": str(derived_ledger_path),
            "human_total_path": None,
            "notes": [
                "Derived holdout case for the autonomous onboarding rehearsal.",
                "Truth events are the source human ledger tail, shifted by the keyframe-aligned split point.",
                "Training-lane stages must never read this ledger; it exists only for the blind replay gate compare.",
            ],
        },
        "runtime": runtime,
        "launch": {
            "backend_port": backend_port,
            "frontend_port": frontend_port,
            "dashboard_url": f"http://127.0.0.1:{frontend_port}/dashboard",
        },
        "proof_artifacts": {
            "observed_events": None,
            "comparison_report": None,
            "validation_report": None,
            "pacing_report": None,
            "screenshots": [],
        },
    }
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _latest_keyframe_at_or_before(keyframes: list[float], target_sec: float) -> float:
    candidates = [keyframe for keyframe in keyframes if keyframe <= max(0.0, target_sec)]
    if candidates:
        return candidates[-1]
    return keyframes[0] if keyframes else max(0.0, target_sec)
