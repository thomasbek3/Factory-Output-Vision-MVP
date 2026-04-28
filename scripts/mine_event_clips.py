#!/usr/bin/env python3
"""Mine likely source-to-output event clips using zone-aware motion scoring."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.calibration import CalibrationZones, box_center, point_in_polygon

MANIFEST_NAME = "manifest.json"
DEFAULT_OUT_DIR = Path("data/events/mined")


@dataclass(frozen=True)
class VideoMetadata:
    duration: float | None
    width: int | None
    height: int | None


@dataclass(frozen=True)
class MotionSample:
    timestamp: float
    source_motion: float
    output_motion: float
    transfer_motion: float
    global_motion: float


@dataclass(frozen=True)
class EventWindow:
    center_timestamp: float
    start_timestamp: float
    end_timestamp: float
    score: float
    source_motion: float
    output_motion: float
    transfer_motion: float
    global_motion: float
    selection_reason: str


MetadataLoader = Callable[[Path], VideoMetadata]
MotionSampler = Callable[..., list[MotionSample]]
ClipExtractor = Callable[..., None]
SheetMaker = Callable[..., None]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine event-rich factory clips using source/output-zone motion.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--clip-seconds", type=float, default=12.0)
    parser.add_argument("--pre-roll-seconds", type=float, default=4.0)
    parser.add_argument("--sample-fps", type=float, default=1.0)
    parser.add_argument("--min-gap-seconds", type=float, default=10.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def safe_video_stem(video_path: Path) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", video_path.stem).strip("._-")
    return safe or "video"


def prepare_output_dir(out_dir: Path, *, force: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{out_dir} already exists and is not empty; pass --force")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "clips").mkdir(parents=True, exist_ok=True)
    (out_dir / "sheets").mkdir(parents=True, exist_ok=True)
    (out_dir / "frames").mkdir(parents=True, exist_ok=True)


def parse_ffprobe_json(payload: dict[str, Any]) -> VideoMetadata:
    duration = _positive_float(payload.get("format", {}).get("duration"))
    width = None
    height = None
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video":
            width = _positive_int(stream.get("width"))
            height = _positive_int(stream.get("height"))
            break
    return VideoMetadata(duration=duration, width=width, height=height)


def ffprobe_metadata(video_path: Path) -> VideoMetadata:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path.resolve()),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return parse_ffprobe_json(json.loads(result.stdout))
    except JSONDecodeError as exc:
        raise ValueError(f"invalid ffprobe JSON for {video_path}") from exc


def load_calibration(calibration_path: Path) -> CalibrationZones:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    source_polygons = _normalize_polygons(payload.get("source_polygons") or [])
    output_polygons = _normalize_polygons(payload.get("output_polygons") or [])
    ignore_polygons = _normalize_polygons(payload.get("ignore_polygons") or [])
    if not source_polygons or not output_polygons:
        raise ValueError("calibration must include source_polygons and output_polygons")
    return CalibrationZones(source_polygons=source_polygons, output_polygons=output_polygons, ignore_polygons=ignore_polygons)


def score_motion_windows(
    samples: list[MotionSample],
    *,
    clip_seconds: float,
    pre_roll_seconds: float,
    limit: int,
    min_gap_seconds: float,
) -> list[EventWindow]:
    if clip_seconds <= 0 or pre_roll_seconds < 0 or limit <= 0 or min_gap_seconds <= 0:
        raise ValueError("clip/pre-roll/limit/min-gap must be positive")
    ranked: list[EventWindow] = []
    for sample in samples:
        zone_balance = min(sample.source_motion, sample.output_motion) * 0.35
        score = sample.transfer_motion * 0.45 + sample.source_motion * 0.25 + sample.output_motion * 0.2 + zone_balance - sample.global_motion * 0.05
        start = max(0.0, sample.timestamp - pre_roll_seconds)
        ranked.append(
            EventWindow(
                center_timestamp=round(sample.timestamp, 3),
                start_timestamp=round(start, 3),
                end_timestamp=round(start + clip_seconds, 3),
                score=round(score, 6),
                source_motion=sample.source_motion,
                output_motion=sample.output_motion,
                transfer_motion=sample.transfer_motion,
                global_motion=sample.global_motion,
                selection_reason="source_output_transfer_motion",
            )
        )

    selected: list[EventWindow] = []
    for window in sorted(ranked, key=lambda item: item.score, reverse=True):
        if any(abs(window.center_timestamp - chosen.center_timestamp) < min_gap_seconds for chosen in selected):
            continue
        selected.append(window)
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda item: item.center_timestamp)


def sample_motion_with_ffmpeg(
    *,
    video_path: Path,
    zones: CalibrationZones,
    metadata: VideoMetadata,
    sample_fps: float,
    work_dir: Path,
) -> list[MotionSample]:
    if sample_fps <= 0 or not math.isfinite(sample_fps):
        raise ValueError("sample_fps must be positive")
    frames_dir = work_dir / "motion_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    pattern = frames_dir / "frame_%06d.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path.resolve()),
            "-vf",
            f"fps={sample_fps:g},scale=320:-1:force_original_aspect_ratio=decrease",
            str(pattern),
        ],
        check=True,
    )
    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
    if len(frame_paths) < 2:
        return []
    return compute_motion_samples_from_frames(
        frame_paths=frame_paths,
        zones=zones,
        original_width=metadata.width or 0,
        original_height=metadata.height or 0,
        sample_fps=sample_fps,
    )


def compute_motion_samples_from_frames(
    *,
    frame_paths: list[Path],
    zones: CalibrationZones,
    original_width: int,
    original_height: int,
    sample_fps: float,
) -> list[MotionSample]:
    import cv2
    import numpy as np

    previous = None
    samples: list[MotionSample] = []
    for index, frame_path in enumerate(frame_paths):
        frame = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
        if frame is None:
            continue
        frame = cv2.GaussianBlur(frame, (5, 5), 0)
        if previous is None:
            previous = frame
            continue
        diff = cv2.absdiff(frame, previous)
        _, mask = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8))
        samples.append(_score_mask(mask, zones, original_width, original_height, timestamp=index / sample_fps))
        previous = frame
    return samples


def extract_clip(*, video_path: Path, output_path: Path, start_timestamp: float, clip_seconds: float, force: bool) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-ss",
            f"{start_timestamp:g}",
            "-i",
            str(video_path.resolve()),
            "-t",
            f"{clip_seconds:g}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-an",
            str(output_path.resolve()),
        ],
        check=True,
    )


def make_contact_sheet(*, video_path: Path, output_path: Path, start_timestamp: float, clip_seconds: float, force: bool) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-ss",
            f"{start_timestamp:g}",
            "-i",
            str(video_path.resolve()),
            "-t",
            f"{clip_seconds:g}",
            "-vf",
            "fps=2,scale=320:-1:force_original_aspect_ratio=decrease,tile=6x4",
            "-frames:v",
            "1",
            str(output_path.resolve()),
        ],
        check=True,
    )


def mine_event_clips(
    *,
    video_path: Path,
    calibration_path: Path,
    out_dir: Path,
    limit: int,
    clip_seconds: float,
    pre_roll_seconds: float,
    sample_fps: float,
    min_gap_seconds: float,
    force: bool,
    metadata_loader: MetadataLoader = ffprobe_metadata,
    motion_sampler: MotionSampler = sample_motion_with_ffmpeg,
    clip_extractor: ClipExtractor = extract_clip,
    sheet_maker: SheetMaker = make_contact_sheet,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    prepare_output_dir(out_dir, force=force)
    zones = load_calibration(calibration_path)
    metadata = metadata_loader(video_path)
    if metadata.duration is None:
        raise ValueError(f"missing valid duration for {video_path}")
    with tempfile.TemporaryDirectory(prefix="factory_event_motion_") as tmp:
        samples = motion_sampler(
            video_path=video_path,
            zones=zones,
            metadata=metadata,
            sample_fps=sample_fps,
            work_dir=Path(tmp),
        )
    windows = score_motion_windows(
        samples,
        clip_seconds=clip_seconds,
        pre_roll_seconds=pre_roll_seconds,
        limit=limit,
        min_gap_seconds=min_gap_seconds,
    )
    events: list[dict[str, Any]] = []
    stem = safe_video_stem(video_path)
    for index, window in enumerate(windows, start=1):
        event_slug = f"{stem}_event_{index:04d}_t{window.center_timestamp:09.2f}"
        clip_path = out_dir / "clips" / f"{event_slug}.mp4"
        sheet_path = out_dir / "sheets" / f"{event_slug}.jpg"
        clip_extractor(video_path=video_path, output_path=clip_path, start_timestamp=window.start_timestamp, clip_seconds=clip_seconds, force=True)
        sheet_maker(video_path=video_path, output_path=sheet_path, start_timestamp=window.start_timestamp, clip_seconds=clip_seconds, force=True)
        events.append(
            {
                "event_id": f"event-{index:04d}",
                "video_path": _repo_relative(video_path, repo_root),
                "clip_path": _repo_relative(clip_path, repo_root),
                "sheet_path": _repo_relative(sheet_path, repo_root),
                "center_timestamp": window.center_timestamp,
                "start_timestamp": window.start_timestamp,
                "end_timestamp": window.end_timestamp,
                "score": window.score,
                "source_motion": window.source_motion,
                "output_motion": window.output_motion,
                "transfer_motion": window.transfer_motion,
                "global_motion": window.global_motion,
                "selection_reason": window.selection_reason,
                "width": metadata.width,
                "height": metadata.height,
                "duration": metadata.duration,
            }
        )
    result = {
        "schema_version": "factory-event-mining-v1",
        "video_path": _repo_relative(video_path, repo_root),
        "calibration_path": _repo_relative(calibration_path, repo_root),
        "sample_fps": sample_fps,
        "clip_seconds": clip_seconds,
        "pre_roll_seconds": pre_roll_seconds,
        "min_gap_seconds": min_gap_seconds,
        "events": events,
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _score_mask(mask: Any, zones: CalibrationZones, original_width: int, original_height: int, *, timestamp: float) -> MotionSample:
    import numpy as np

    height, width = mask.shape[:2]
    sx = original_width / width if original_width else 1.0
    sy = original_height / height if original_height else 1.0
    source_pixels = output_pixels = transfer_pixels = global_pixels = 0
    active_pixels = np.argwhere(mask > 0)
    for y, x in active_pixels:
        original_point = (float(x) * sx, float(y) * sy)
        in_source = any(point_in_polygon(original_point, polygon) for polygon in zones.source_polygons)
        in_output = any(point_in_polygon(original_point, polygon) for polygon in zones.output_polygons)
        if in_source:
            source_pixels += 1
        if in_output:
            output_pixels += 1
        if in_source or in_output or _between_zone_centers(original_point, zones):
            transfer_pixels += 1
        global_pixels += 1
    total = max(1, width * height)
    return MotionSample(
        timestamp=round(timestamp, 3),
        source_motion=source_pixels / total,
        output_motion=output_pixels / total,
        transfer_motion=transfer_pixels / total,
        global_motion=global_pixels / total,
    )


def _between_zone_centers(point: tuple[float, float], zones: CalibrationZones) -> bool:
    source_centers = [_polygon_center(polygon) for polygon in zones.source_polygons]
    output_centers = [_polygon_center(polygon) for polygon in zones.output_polygons]
    if not source_centers or not output_centers:
        return False
    sx, sy = source_centers[0]
    ox, oy = output_centers[0]
    min_x, max_x = sorted((sx, ox))
    min_y, max_y = sorted((sy, oy))
    pad_x = abs(max_x - min_x) * 0.25 + 40
    pad_y = abs(max_y - min_y) * 0.35 + 40
    return min_x - pad_x <= point[0] <= max_x + pad_x and min_y - pad_y <= point[1] <= max_y + pad_y


def _polygon_center(polygon: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _normalize_polygons(value: Any) -> list[list[tuple[float, float]]]:
    polygons = []
    for polygon in value:
        points = [(float(point[0]), float(point[1])) for point in polygon]
        if len(points) < 3:
            raise ValueError("polygons must have at least 3 points")
        polygons.append(points)
    return polygons


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = mine_event_clips(
            video_path=args.video,
            calibration_path=args.calibration,
            out_dir=args.out_dir,
            limit=args.limit,
            clip_seconds=args.clip_seconds,
            pre_roll_seconds=args.pre_roll_seconds,
            sample_fps=args.sample_fps,
            min_gap_seconds=args.min_gap_seconds,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
