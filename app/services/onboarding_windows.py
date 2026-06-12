from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.services.stream_recorder import validate_segment_manifest


SCHEMA_VERSION = "factory-vision-onboarding-window-manifest-v1"
CANDIDATE_TYPES = ("positive_candidate", "idle_candidate", "hard_negative_candidate")


def extract_candidate_windows(
    *,
    segment_manifest_path: Path,
    output_dir: Path,
    window_sec: float = 1.0,
    force: bool = False,
) -> dict[str, Any]:
    if window_sec <= 0:
        raise ValueError("window_sec must be positive")
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    validate_segment_manifest(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    windows: list[dict[str, Any]] = []
    for segment in manifest["segments"]:
        if not segment.get("decode_ok"):
            continue
        duration = _duration_for_sampling(segment)
        for candidate_type, offset in _candidate_offsets(duration, window_sec=window_sec).items():
            window_id = f"{segment['segment_id']}_{candidate_type}"
            clip_path = output_dir / f"{window_id}.mp4"
            if clip_path.exists() and not force:
                raise FileExistsError(f"{clip_path} already exists; pass --force to overwrite")
            _extract_clip(
                source=Path(segment["path"]),
                output=clip_path,
                start_offset_sec=offset,
                duration_sec=min(window_sec, duration),
            )
            windows.append(
                {
                    "station_id": manifest["station_id"],
                    "window_id": window_id,
                    "segment_id": segment["segment_id"],
                    "segment_path": segment["path"],
                    "clip_path": str(clip_path),
                    "candidate_type": candidate_type,
                    "start_offset_sec": round(offset, 3),
                    "duration_sec": round(min(window_sec, duration), 3),
                    "source_start_wall_ts": segment.get("start_wall_ts"),
                    "source_end_wall_ts": segment.get("end_wall_ts"),
                    "label_status": "unreviewed",
                    "evidence_role": "candidate_only_not_truth",
                    "generated_by": "fixed_offset_segment_sampler_v1",
                }
            )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "station_id": manifest["station_id"],
        "segment_manifest_path": str(segment_manifest_path),
        "window_sec": float(window_sec),
        "candidate_types": list(CANDIDATE_TYPES),
        "windows": windows,
    }
    manifest_out = output_dir / "window_manifest.json"
    if manifest_out.exists() and not force:
        raise FileExistsError(f"{manifest_out} already exists; pass --force to overwrite")
    manifest_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _duration_for_sampling(segment: dict[str, Any]) -> float:
    duration = segment.get("duration_sec")
    if duration is None:
        raise ValueError(f"segment {segment.get('segment_id')} missing duration_sec")
    parsed = float(duration)
    if parsed <= 0:
        raise ValueError(f"segment {segment.get('segment_id')} duration_sec must be positive")
    return parsed


def _candidate_offsets(duration: float, *, window_sec: float) -> dict[str, float]:
    last_offset = max(0.0, duration - window_sec)
    middle_offset = max(0.0, (duration / 2.0) - (window_sec / 2.0))
    return {
        "idle_candidate": 0.0,
        "positive_candidate": middle_offset,
        "hard_negative_candidate": last_offset,
    }


def _extract_clip(*, source: Path, output: Path, start_offset_sec: float, duration_sec: float) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_offset_sec:.3f}",
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
