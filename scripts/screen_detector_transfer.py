#!/usr/bin/env python3
"""Screen whether existing YOLO detectors transfer to a new candidate video."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Protocol


class Detector(Protocol):
    def predict(self, source: Any, conf: float, verbose: bool) -> list[Any]:
        ...


def ffprobe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def uniform_timestamps(duration_sec: float, sample_count: int) -> list[float]:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    return [round(((index + 0.5) / sample_count) * duration_sec, 3) for index in range(sample_count)]


def read_frame_at(video_path: Path, timestamp_sec: float) -> Any:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("frame sampling requires cv2; use the repo .venv") from exc

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s")
    return frame


def load_yolo_model(model_path: Path) -> Detector:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("detector screening requires ultralytics; use the repo .venv") from exc
    return YOLO(str(model_path))


def _box_confidences(result: Any) -> list[float]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    confs = getattr(boxes, "conf", None)
    if confs is None:
        return []
    if hasattr(confs, "detach"):
        confs = confs.detach()
    if hasattr(confs, "cpu"):
        confs = confs.cpu()
    if hasattr(confs, "numpy"):
        return [float(value) for value in confs.numpy().tolist()]
    return [float(value) for value in confs]


def _recommendation(detection_rate: float) -> str:
    if detection_rate <= 0.10:
        return "transfer_failed_build_video_specific_detector"
    if detection_rate >= 0.95:
        return "broad_or_static_detector_risk_requires_runtime_diagnostic"
    return "plausible_transfer_candidate_run_fast_diagnostic"


def screen_detector(
    *,
    detector: Detector,
    model_path: Path,
    frames: list[Any],
    confidences: list[float],
) -> dict[str, Any]:
    min_confidence = min(confidences)
    confidence_rows = {
        confidence: {"images_with_detections": 0, "total_detections": 0}
        for confidence in confidences
    }
    for frame in frames:
        results = detector.predict(source=frame, conf=min_confidence, verbose=False)
        confidences_for_frame: list[float] = []
        for result in results:
            confidences_for_frame.extend(_box_confidences(result))
        for confidence, row in confidence_rows.items():
            hits = [value for value in confidences_for_frame if value >= confidence]
            if hits:
                row["images_with_detections"] += 1
            row["total_detections"] += len(hits)

    summaries: list[dict[str, Any]] = []
    sample_count = len(frames)
    for confidence in sorted(confidence_rows):
        row = confidence_rows[confidence]
        detection_rate = row["images_with_detections"] / sample_count if sample_count else 0.0
        summaries.append(
            {
                "confidence": confidence,
                "images_with_detections": row["images_with_detections"],
                "sample_count": sample_count,
                "detection_rate": round(detection_rate, 4),
                "total_detections": row["total_detections"],
                "recommendation": _recommendation(detection_rate),
            }
        )
    return {"model_path": model_path.as_posix(), "confidence_summaries": summaries}


def screen_video(
    *,
    video_path: Path,
    model_paths: list[Path],
    sample_count: int,
    confidences: list[float],
) -> dict[str, Any]:
    duration_sec = ffprobe_duration(video_path)
    timestamps = uniform_timestamps(duration_sec, sample_count)
    frames = [read_frame_at(video_path, timestamp) for timestamp in timestamps]
    models = [
        screen_detector(
            detector=load_yolo_model(model_path),
            model_path=model_path,
            frames=frames,
            confidences=confidences,
        )
        for model_path in model_paths
    ]
    return {
        "schema_version": "factory-vision-detector-transfer-screen-v1",
        "video_path": video_path.as_posix(),
        "duration_sec": round(duration_sec, 3),
        "sample_count": sample_count,
        "sample_timestamps_sec": timestamps,
        "models": models,
    }


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Screen detector transfer on uniformly sampled video frames")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model", type=Path, action="append", required=True)
    parser.add_argument("--sample-count", type=int, default=80)
    parser.add_argument("--confidence", type=float, action="append", default=[0.25])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = screen_video(
        video_path=args.video,
        model_paths=args.model,
        sample_count=args.sample_count,
        confidences=sorted(set(args.confidence)),
    )
    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": args.output.as_posix(), "model_count": len(payload["models"])}))


if __name__ == "__main__":
    main()
