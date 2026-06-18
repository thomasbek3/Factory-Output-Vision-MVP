from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np

from app.services.zone_tripwire import ZoneCropper, load_output_zone_polygon, sample_timestamps

Encoding = Literal["stack3", "clip", "flow"]
SCHEMA_VERSION = "factory-vision-clip-dataset-v1"
ENCODINGS: tuple[Encoding, ...] = ("stack3", "clip", "flow")


def extract_clip_dataset(
    *,
    candidates: list[dict[str, Any]],
    output_dir: Path,
    output_zone_polygon: list[list[float]],
    default_video_path: Path | None = None,
    encoding: Encoding | Literal["all"] = "clip",
    clip_fps: float = 6.0,
    clip_frame_count: int = 16,
) -> dict[str, Any]:
    if clip_fps <= 0:
        raise ValueError("clip_fps must be positive")
    if clip_frame_count <= 1:
        raise ValueError("clip_frame_count must be greater than 1")
    requested = list(ENCODINGS) if encoding == "all" else [encoding]
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        candidate_id = str(candidate.get("candidate_id") or f"candidate-{index + 1:05d}")
        source_path = _candidate_source_path(candidate, default_video_path)
        start_sec = float(candidate.get("start_sec", candidate.get("start_offset_sec", 0.0)))
        end_sec = float(candidate.get("end_sec", candidate.get("end_offset_sec", start_sec)))
        center_sec = float(candidate.get("center_sec", candidate.get("center_offset_sec", (start_sec + end_sec) / 2.0)))
        frames = decode_zone_clip(
            video_path=source_path,
            output_zone_polygon=output_zone_polygon,
            start_sec=start_sec,
            end_sec=end_sec,
            clip_fps=clip_fps,
            clip_frame_count=clip_frame_count,
        )
        paths: dict[str, str] = {}
        for item in requested:
            npz_path = output_dir / f"{sample_hash(candidate=candidate, source_path=source_path, encoding=item, clip_fps=clip_fps, clip_frame_count=clip_frame_count)}.{item}.npz"
            if not npz_path.exists():
                array = encode_frames(frames, encoding=item)
                np.savez_compressed(npz_path, data=array)
            paths[item] = str(npz_path)
        rows.append(
            {
                "candidate_id": candidate_id,
                "source": str(source_path),
                "center_sec": center_sec,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "paths": paths,
                "label": candidate.get("label"),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "clip_fps": float(clip_fps),
        "clip_frame_count": int(clip_frame_count),
        "encodings": requested,
        "samples": rows,
    }


def decode_zone_clip(
    *,
    video_path: Path,
    output_zone_polygon: list[list[float]],
    start_sec: float,
    end_sec: float,
    clip_fps: float,
    clip_frame_count: int,
) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("clip extraction requires cv2; use the repo .venv") from exc
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if end_sec < start_sec:
        raise ValueError("candidate end_sec must be >= start_sec")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    frames: list[np.ndarray] = []
    cropper: ZoneCropper | None = None
    try:
        timestamps = _clip_timestamps(start_sec=start_sec, end_sec=end_sec, clip_fps=clip_fps, clip_frame_count=clip_frame_count)
        for timestamp_sec in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            if cropper is None:
                cropper = ZoneCropper(frame_shape=frame.shape, polygon=output_zone_polygon)
            crop = cropper.crop(frame)
            frames.append(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()
    if not frames:
        raise RuntimeError(f"no frames decoded from {video_path}")
    frames = pad_or_trim_frames(frames, clip_frame_count)
    return np.stack(frames, axis=0).astype(np.uint8)


def encode_frames(frames_rgb: np.ndarray, *, encoding: Encoding) -> np.ndarray:
    if frames_rgb.ndim != 4 or frames_rgb.shape[-1] != 3:
        raise ValueError("frames_rgb must have shape T,H,W,3")
    if encoding == "clip":
        return frames_rgb
    if encoding == "stack3":
        indexes = [0, len(frames_rgb) // 2, len(frames_rgb) - 1]
        return frames_rgb[indexes]
    if encoding == "flow":
        return optical_flow(frames_rgb)
    raise ValueError(f"unsupported encoding: {encoding}")


def optical_flow(frames_rgb: np.ndarray) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("flow encoding requires cv2; use the repo .venv") from exc
    if len(frames_rgb) < 2:
        height, width = frames_rgb.shape[1:3]
        return np.zeros((1, height, width, 2), dtype=np.float32)
    gray = [cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) for frame in frames_rgb]
    flows = []
    for before, after in zip(gray, gray[1:]):
        flow = cv2.calcOpticalFlowFarneback(before, after, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        flows.append(flow.astype(np.float32))
    return np.stack(flows, axis=0)


def write_clip_manifest(path: Path, manifest: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if "candidates" in payload:
        return list(payload["candidates"])
    if "samples" in payload:
        return list(payload["samples"])
    raise ValueError("candidate file must be a list or contain candidates/samples")


def load_clip_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported clip manifest schema: {payload.get('schema_version')}")
    return payload


def sample_hash(
    *,
    candidate: dict[str, Any],
    source_path: Path,
    encoding: Encoding,
    clip_fps: float,
    clip_frame_count: int,
) -> str:
    payload = {
        "candidate_id": candidate.get("candidate_id"),
        "source": str(source_path),
        "start_sec": candidate.get("start_sec", candidate.get("start_offset_sec")),
        "end_sec": candidate.get("end_sec", candidate.get("end_offset_sec")),
        "center_sec": candidate.get("center_sec", candidate.get("center_offset_sec")),
        "encoding": encoding,
        "clip_fps": clip_fps,
        "clip_frame_count": clip_frame_count,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def pad_or_trim_frames(frames: list[np.ndarray], target_count: int) -> list[np.ndarray]:
    if len(frames) >= target_count:
        if len(frames) == target_count:
            return frames
        indexes = np.linspace(0, len(frames) - 1, num=target_count).round().astype(int)
        return [frames[int(index)] for index in indexes]
    padded = list(frames)
    while len(padded) < target_count:
        padded.append(frames[-1].copy())
    return padded


def _clip_timestamps(*, start_sec: float, end_sec: float, clip_fps: float, clip_frame_count: int) -> list[float]:
    duration = max(0.0, end_sec - start_sec)
    raw = [start_sec + timestamp for timestamp in sample_timestamps(duration_sec=duration, sample_fps=clip_fps)]
    if len(raw) >= clip_frame_count:
        indexes = np.linspace(0, len(raw) - 1, num=clip_frame_count).round().astype(int)
        return [raw[int(index)] for index in indexes]
    if not raw:
        raw = [start_sec]
    while len(raw) < clip_frame_count:
        raw.append(raw[-1])
    return raw


def _candidate_source_path(candidate: dict[str, Any], default_video_path: Path | None) -> Path:
    source = candidate.get("source") or candidate.get("segment_path")
    if source:
        return Path(str(source)).expanduser()
    if default_video_path is not None:
        return default_video_path.expanduser()
    raise ValueError("candidate source missing and no default_video_path supplied")


def output_zone_from_calibration(path: Path) -> list[list[float]]:
    return load_output_zone_polygon(path)
