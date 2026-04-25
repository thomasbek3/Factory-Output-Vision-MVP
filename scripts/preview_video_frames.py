#!/usr/bin/env python3
"""Generate ffmpeg contact sheets for one or more videos."""

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


DEFAULT_OUT_DIR = Path("data/videos/preview_sheets")
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class VideoMetadata:
    duration: float | None
    width: int | None
    height: int | None


def safe_video_stem(video_path: Path) -> str:
    """Return a readable filename stem safe for repo-local generated files."""
    raw_stem = video_path.stem
    if raw_stem == video_path.name and re.fullmatch(r"\.[A-Za-z0-9]+", raw_stem):
        raw_stem = ""
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_stem).strip("._-")
    return safe_stem or "video"


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


def calculate_sample_interval(duration: float | None, frames: int) -> float:
    if frames <= 0:
        raise ValueError("frames must be positive")
    if duration is None or duration <= 0:
        return 1.0
    return duration / frames


def build_ffmpeg_filter(interval: float, cols: int, rows: int) -> str:
    if interval <= 0:
        raise ValueError("interval must be positive")
    if cols <= 0:
        raise ValueError("cols must be positive")
    if rows <= 0:
        raise ValueError("rows must be positive")
    return (
        f"fps=1/{interval:g},"
        "scale=320:-1:force_original_aspect_ratio=decrease,"
        f"tile={cols}x{rows}"
    )


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
    output_path: Path,
    metadata: VideoMetadata,
    interval: float,
    frames: int,
    cols: int,
    rows: int,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "video_path": _repo_relative(video_path, repo_root),
        "duration": metadata.duration,
        "sheet_path": _repo_relative(output_path, repo_root),
        "sampled_interval": interval,
        "frames": frames,
        "cols": cols,
        "rows": rows,
        "width": metadata.width,
        "height": metadata.height,
    }


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


def build_ffmpeg_command(
    *,
    video_path: Path,
    output_path: Path,
    interval: float,
    cols: int,
    rows: int,
    force: bool,
) -> list[str]:
    overwrite_flag = "-y" if force else "-n"
    resolved_video_path = video_path.resolve()
    resolved_output_path = output_path.resolve()
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        overwrite_flag,
        "-i",
        str(resolved_video_path),
        "-vf",
        build_ffmpeg_filter(interval, cols, rows),
        "-frames:v",
        "1",
        str(resolved_output_path),
    ]


def run_ffmpeg_contact_sheet(
    *,
    video_path: Path,
    output_path: Path,
    interval: float,
    cols: int,
    rows: int,
    force: bool,
) -> None:
    command = build_ffmpeg_command(
        video_path=video_path,
        output_path=output_path,
        interval=interval,
        cols=cols,
        rows=rows,
        force=force,
    )
    subprocess.run(command, check=True)


def unique_output_path(video_path: Path, out_dir: Path, used: set[Path]) -> Path:
    base = safe_video_stem(video_path)
    candidate = out_dir / f"{base}.jpg"
    index = 2
    while candidate in used:
        candidate = out_dir / f"{base}_{index}.jpg"
        index += 1
    used.add(candidate)
    return candidate


def generate_previews(
    *,
    video_paths: list[Path],
    out_dir: Path,
    frames: int,
    cols: int,
    force: bool,
    repo_root: Path,
) -> list[dict[str, Any]]:
    if frames <= 0:
        raise ValueError("--frames must be positive")
    if cols <= 0:
        raise ValueError("--cols must be positive")

    rows = math.ceil(frames / cols)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / MANIFEST_NAME
    if manifest_path.exists() and not force:
        raise FileExistsError(f"{manifest_path} already exists; pass --force to overwrite")

    manifest_rows = []
    used_paths: set[Path] = set()
    for video_path in video_paths:
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        output_path = unique_output_path(video_path, out_dir, used_paths)
        if output_path.exists() and not force:
            raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")

        metadata = ffprobe_metadata(video_path)
        interval = calculate_sample_interval(metadata.duration, frames)
        run_ffmpeg_contact_sheet(
            video_path=video_path,
            output_path=output_path,
            interval=interval,
            cols=cols,
            rows=rows,
            force=force,
        )
        manifest_rows.append(
            build_manifest_row(
                video_path=video_path,
                output_path=output_path,
                metadata=metadata,
                interval=interval,
                frames=frames,
                cols=cols,
                rows=rows,
                repo_root=repo_root,
            )
        )

    manifest_path.write_text(json.dumps(manifest_rows, indent=2) + "\n", encoding="utf-8")
    return manifest_rows


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate JPG contact sheets for one or more videos using ffprobe/ffmpeg."
    )
    parser.add_argument("videos", nargs="+", type=Path, help="Video path(s) to preview")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing contact sheets and manifest.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rows = generate_previews(
            video_paths=args.videos,
            out_dir=args.out_dir,
            frames=args.frames,
            cols=args.cols,
            force=args.force,
            repo_root=Path.cwd(),
        )
    except (FileExistsError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(rows)} preview sheet(s) and {args.out_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
