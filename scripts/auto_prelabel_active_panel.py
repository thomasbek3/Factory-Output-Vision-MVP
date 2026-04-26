#!/usr/bin/env python3
"""Generate active-panel label candidates from selected real frames."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable


DEFAULT_MANIFEST = Path("data/videos/selected_frames/autopilot-v1/manifest.json")
DEFAULT_OUTPUT = Path("data/labels/active_panel_candidates.json")
DEFAULT_MODEL_PATHS = [
    Path("models/panel_in_transit.pt"),
    Path("models/caleb_metal_panel.pt"),
]
SCHEMA_VERSION = "active-panel-candidates-v1"

DetectionRunner = Callable[..., list[dict[str, Any]]]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-prelabel active panel candidates from selected frame manifests."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--model",
        action="append",
        type=Path,
        default=[],
        help="YOLO .pt model path. Repeat to run multiple models.",
    )
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing output manifest")
    return parser.parse_args(argv)


def safe_label_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return safe or "label"


def frame_id_from_path(frame_path: str | Path) -> str:
    return safe_label_id(Path(frame_path).stem)


def choose_model_paths(
    explicit_model_paths: list[Path],
    *,
    repo_root: Path = Path("."),
) -> list[Path]:
    if explicit_model_paths:
        return explicit_model_paths
    return [repo_root / path for path in DEFAULT_MODEL_PATHS if (repo_root / path).exists()]


def load_selected_frames_manifest(
    manifest_path: Path,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be non-negative")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("selected frame manifest must be a list")

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"manifest row {index} must be an object")
        rows.append(_normalize_frame_row(row, index=index))
        if limit is not None and len(rows) >= limit:
            break
    return rows


def normalize_box_xyxy(box: Any, *, width: int, height: int) -> list[int | float]:
    try:
        x1, y1, x2, y2 = [float(value) for value in box]
    except (TypeError, ValueError) as exc:
        raise ValueError("box must contain four numeric xyxy values") from exc

    if not all(math.isfinite(value) for value in [x1, y1, x2, y2]):
        raise ValueError("box values must be finite")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")

    clipped = [
        min(max(x1, 0.0), float(width)),
        min(max(y1, 0.0), float(height)),
        min(max(x2, 0.0), float(width)),
        min(max(y2, 0.0), float(height)),
    ]
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        raise ValueError("degenerate box after clipping")
    return [_json_number(value) for value in clipped]


def build_candidate_label(
    frame: dict[str, Any],
    detection: dict[str, Any],
    *,
    model_path: Path,
    detection_index: int,
) -> dict[str, Any]:
    frame_path = str(frame["frame_path"])
    video_path = str(frame["video_path"])
    timestamp = float(frame["timestamp_seconds"])
    image_width = int(frame["width"])
    image_height = int(frame["height"])
    class_index = detection.get("class_index")
    class_name = detection.get("class_name")

    frame_path_stem = Path(frame_path).with_suffix("").as_posix()
    return {
        "label_id": safe_label_id(f"{frame_path_stem}-active_panel-{detection_index:03d}"),
        "frame_id": frame_id_from_path(frame_path),
        "image_width": image_width,
        "image_height": image_height,
        "class_name": "active_panel",
        "box": normalize_box_xyxy(detection["box"], width=image_width, height=image_height),
        "confidence": float(detection["confidence"]),
        "source_type": "box",
        "metadata": {
            "model_path": model_path.as_posix(),
            "model_class_name": str(class_name) if class_name is not None else None,
            "model_class_index": int(class_index) if class_index is not None else None,
            "frame_path": frame_path,
            "video_path": video_path,
            "timestamp_seconds": timestamp,
        },
    }


def write_candidate_manifest(
    labels: list[dict[str, Any]],
    *,
    output_path: Path,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    manifest = {"schema_version": SCHEMA_VERSION, "labels": labels}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def run_prelabel(
    *,
    manifest_path: Path,
    output_path: Path,
    model_paths: list[Path],
    confidence: float,
    limit: int | None,
    force: bool,
    detector_runner: DetectionRunner | None = None,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    if not model_paths:
        raise ValueError("No model paths found; pass --model or run from a repo with default models")
    if confidence < 0 or confidence > 1 or not math.isfinite(confidence):
        raise ValueError("--confidence must be between 0 and 1")

    runner = detector_runner or run_yolo_detector
    frames = load_selected_frames_manifest(manifest_path, limit=limit)
    labels: list[dict[str, Any]] = []
    for frame in frames:
        frame_path = _resolve_frame_path(Path(frame["frame_path"]), manifest_path=manifest_path)
        runner_frame = {**frame, "frame_path": frame_path.as_posix()}
        for model_path in model_paths:
            detections = runner(
                frame_path=frame_path,
                model_path=model_path,
                confidence=confidence,
            )
            for detection in detections:
                try:
                    labels.append(
                        build_candidate_label(
                            runner_frame,
                            detection,
                            model_path=model_path,
                            detection_index=len(labels),
                        )
                    )
                except ValueError:
                    continue

    return write_candidate_manifest(labels, output_path=output_path, force=force)


def _resolve_frame_path(frame_path: Path, *, manifest_path: Path) -> Path:
    if frame_path.is_absolute() or frame_path.exists():
        return frame_path
    candidate = manifest_path.parent / frame_path
    if candidate.exists():
        return candidate
    return frame_path


def run_yolo_detector(*, frame_path: Path, model_path: Path, confidence: float) -> list[dict[str, Any]]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    results = model.predict(str(frame_path), conf=confidence, verbose=False)
    detections: list[dict[str, Any]] = []
    for result in results:
        names = getattr(result, "names", {}) or getattr(model, "names", {})
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        xyxy_values = _to_list(getattr(boxes, "xyxy", []))
        confidence_values = _to_list(getattr(boxes, "conf", []))
        class_values = _to_list(getattr(boxes, "cls", []))
        for box, score, class_index in zip(xyxy_values, confidence_values, class_values):
            class_index_int = int(class_index)
            detections.append(
                {
                    "box": box,
                    "confidence": float(score),
                    "class_index": class_index_int,
                    "class_name": names.get(class_index_int, str(class_index_int))
                    if isinstance(names, dict)
                    else str(class_index_int),
                }
            )
    return detections


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        model_paths = choose_model_paths(args.model, repo_root=Path.cwd())
        run_prelabel(
            manifest_path=args.manifest,
            output_path=args.output,
            model_paths=model_paths,
            confidence=args.confidence,
            limit=args.limit,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, ValueError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _normalize_frame_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    timestamp = row.get("timestamp_seconds", row.get("timestamp"))
    required_values = {
        "frame_path": row.get("frame_path"),
        "video_path": row.get("video_path"),
        "timestamp_seconds": timestamp,
        "width": row.get("width"),
        "height": row.get("height"),
    }
    missing = [key for key, value in required_values.items() if value is None]
    if missing:
        raise ValueError(f"manifest row {index} missing required field(s): {', '.join(missing)}")
    return {
        "frame_path": str(required_values["frame_path"]),
        "video_path": str(required_values["video_path"]),
        "timestamp_seconds": float(required_values["timestamp_seconds"]),
        "width": int(required_values["width"]),
        "height": int(required_values["height"]),
    }


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def _json_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


if __name__ == "__main__":
    raise SystemExit(main())
