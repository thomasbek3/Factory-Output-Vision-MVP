#!/usr/bin/env python3
"""Select deterministic review/training frame candidates from long videos."""

from __future__ import annotations

import argparse
import json
from json import JSONDecodeError
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_OUT_DIR = Path("data/videos/selected_frames")
DEFAULT_FRAMES_PER_VIDEO = 80
DEFAULT_MIN_INTERVAL_SECONDS = 2.0
DEFAULT_SCENE_THRESHOLD = 0.18
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class VideoMetadata:
    duration: float | None
    width: int | None
    height: int | None


@dataclass(frozen=True)
class TimestampCandidate:
    timestamp: float
    selection_reason: str


def safe_video_stem(video_path: Path) -> str:
    """Return a readable filename stem safe for repo-local generated files."""
    raw_stem = video_path.stem
    if raw_stem == video_path.name and re.fullmatch(r"\.[A-Za-z0-9]+", raw_stem):
        raw_stem = ""
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_stem).strip("._-")
    return safe_stem or "video"


def safe_frame_filename(video_path: Path, timestamp: float) -> str:
    if timestamp < 0 or not math.isfinite(timestamp):
        raise ValueError("timestamp must be a non-negative finite number")
    return f"{safe_video_stem(video_path)}_t{timestamp:09.2f}.jpg"


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def parse_ffprobe_json(payload: dict[str, Any]) -> VideoMetadata:
    duration = _positive_float(payload.get("format", {}).get("duration"))
    width = None
    height = None

    for stream in payload.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        width = _positive_int(stream.get("width"))
        height = _positive_int(stream.get("height"))
        break

    return VideoMetadata(duration=duration, width=width, height=height)


def ffprobe_metadata(video_path: Path) -> VideoMetadata:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path.resolve()),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except JSONDecodeError as exc:
        raise ValueError(f"invalid ffprobe JSON for {video_path}") from exc
    return parse_ffprobe_json(payload)


def uniform_timestamps(duration: float, frames_per_video: int) -> list[float]:
    if duration <= 0 or not math.isfinite(duration):
        raise ValueError("duration must be a positive finite number")
    if frames_per_video <= 0:
        raise ValueError("frames_per_video must be positive")
    interval = duration / frames_per_video
    return [round((index + 0.5) * interval, 3) for index in range(frames_per_video)]


def filter_min_interval(
    candidates: list[TimestampCandidate],
    *,
    min_interval_seconds: float,
    limit: int,
) -> list[TimestampCandidate]:
    if min_interval_seconds <= 0 or not math.isfinite(min_interval_seconds):
        raise ValueError("min interval must be a positive finite number")
    if limit <= 0:
        raise ValueError("limit must be positive")

    selected: list[TimestampCandidate] = []
    last_timestamp: float | None = None
    seen_timestamps: set[float] = set()
    for candidate in sorted(candidates, key=lambda item: item.timestamp):
        if candidate.timestamp in seen_timestamps:
            continue
        seen_timestamps.add(candidate.timestamp)
        if last_timestamp is not None and candidate.timestamp - last_timestamp < min_interval_seconds:
            continue
        selected.append(candidate)
        last_timestamp = candidate.timestamp
        if len(selected) >= limit:
            break
    return selected


def _repo_relative(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = repo_root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return str(path)


def build_manifest_row(
    *,
    video_path: Path,
    frame_path: Path,
    timestamp: float,
    selection_reason: str,
    metadata: VideoMetadata,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "video_path": _repo_relative(video_path, repo_root),
        "frame_path": _repo_relative(frame_path, repo_root),
        "timestamp_seconds": timestamp,
        "selection_reason": selection_reason,
        "width": metadata.width,
        "height": metadata.height,
        "duration": metadata.duration,
    }


def build_extract_frame_command(
    *,
    video_path: Path,
    frame_path: Path,
    timestamp: float,
    force: bool,
) -> list[str]:
    if timestamp < 0 or not math.isfinite(timestamp):
        raise ValueError("timestamp must be a non-negative finite number")
    overwrite_flag = "-y" if force else "-n"
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        overwrite_flag,
        "-ss",
        f"{timestamp:g}",
        "-i",
        str(video_path.resolve()),
        "-frames:v",
        "1",
        str(frame_path.resolve()),
    ]


def extract_frame(*, video_path: Path, frame_path: Path, timestamp: float, force: bool) -> None:
    command = build_extract_frame_command(
        video_path=video_path,
        frame_path=frame_path,
        timestamp=timestamp,
        force=force,
    )
    subprocess.run(command, check=True)


def select_frames(
    *,
    video_paths: list[Path],
    out_dir: Path,
    frames_per_video: int,
    min_interval_seconds: float,
    scene_threshold: float,
    force: bool,
    repo_root: Path,
) -> list[dict[str, Any]]:
    if frames_per_video <= 0:
        raise ValueError("--frames-per-video must be positive")
    if min_interval_seconds <= 0 or not math.isfinite(min_interval_seconds):
        raise ValueError("--min-interval-seconds must be a positive finite number")
    if scene_threshold <= 0 or not math.isfinite(scene_threshold):
        raise ValueError("--scene-threshold must be a positive finite number")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / MANIFEST_NAME
    if manifest_path.exists() and not force:
        raise FileExistsError(f"{manifest_path} manifest already exists; pass --force to overwrite")

    manifest_rows: list[dict[str, Any]] = []
    planned_frames: set[Path] = set()
    for video_path in video_paths:
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        metadata = ffprobe_metadata(video_path)
        if metadata.duration is None:
            raise ValueError(f"missing valid duration for {video_path}")

        candidates = [
            TimestampCandidate(timestamp=timestamp, selection_reason="uniform")
            for timestamp in uniform_timestamps(metadata.duration, frames_per_video)
        ]
        selected = filter_min_interval(
            candidates,
            min_interval_seconds=min_interval_seconds,
            limit=frames_per_video,
        )

        for candidate in selected:
            frame_path = out_dir / safe_frame_filename(video_path, candidate.timestamp)
            if frame_path in planned_frames:
                raise FileExistsError(f"{frame_path} would be written more than once")
            planned_frames.add(frame_path)
            if frame_path.exists() and not force:
                raise FileExistsError(f"{frame_path} already exists; pass --force to overwrite")

            extract_frame(
                video_path=video_path,
                frame_path=frame_path,
                timestamp=candidate.timestamp,
                force=force,
            )
            manifest_rows.append(
                build_manifest_row(
                    video_path=video_path,
                    frame_path=frame_path,
                    timestamp=candidate.timestamp,
                    selection_reason=candidate.selection_reason,
                    metadata=metadata,
                    repo_root=repo_root,
                )
            )

    manifest_path.write_text(json.dumps(manifest_rows, indent=2) + "\n", encoding="utf-8")
    return manifest_rows


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select deterministic JPG training/review frames from one or more videos."
    )
    parser.add_argument("videos", nargs="+", type=Path, help="Video path(s) to sample")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--frames-per-video", type=int, default=DEFAULT_FRAMES_PER_VIDEO)
    parser.add_argument(
        "--min-interval-seconds",
        type=float,
        default=DEFAULT_MIN_INTERVAL_SECONDS,
    )
    parser.add_argument("--scene-threshold", type=float, default=DEFAULT_SCENE_THRESHOLD)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing selected frames and manifest.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rows = select_frames(
            video_paths=args.videos,
            out_dir=args.out_dir,
            frames_per_video=args.frames_per_video,
            min_interval_seconds=args.min_interval_seconds,
            scene_threshold=args.scene_threshold,
            force=args.force,
            repo_root=Path.cwd(),
        )
    except (FileExistsError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(rows)} selected frame(s) and {args.out_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
