#!/usr/bin/env python3
"""Evaluate active_panel detector recall/localization on reviewed positive images.

This complements the hard-negative false-positive harness: hard negatives tell us
what the model should not count; reviewed positives tell us whether the detector
still sees the active panel at all.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval_detector_false_positives import (
    IMAGE_EXTENSIONS,
    parse_simple_yaml,
    resolve_dataset_manifest,
    run_yolo_detector,
)

SCHEMA_VERSION = "active-panel-positive-detector-eval-v1"
DetectionRunner = Callable[..., dict[str, list[dict[str, Any]]]]
ImageSizeProvider = Callable[[Path], tuple[int, int]]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def image_for_label_path(label_path: Path) -> Optional[Path]:
    parts = list(label_path.parts)
    try:
        index = parts.index("labels")
    except ValueError:
        return None
    parts[index] = "images"
    image_dir = Path(*parts[:-1])
    for suffix in IMAGE_EXTENSIONS:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def load_positive_items(*, data_yaml: Optional[Path], dataset_manifest: Optional[Path]) -> list[dict[str, Any]]:
    manifest_path = resolve_dataset_manifest(data_yaml=data_yaml, dataset_manifest=dataset_manifest)
    if manifest_path is not None:
        payload = load_json(manifest_path)
        if payload.get("schema_version") != "active-panel-yolo-dataset-v1":
            raise ValueError("Expected dataset manifest schema_version active-panel-yolo-dataset-v1")
        rows: list[dict[str, Any]] = []
        for item in payload.get("items") or []:
            if item.get("kind") == "positive":
                rows.append(
                    {
                        "positive_id": item.get("label_id") or Path(str(item.get("image_path"))).stem,
                        "image_path": str(item.get("image_path")),
                        "label_path": str(item.get("label_path")),
                        "class_name": item.get("class_name") or "active_panel",
                        "split": item.get("split") or "train",
                    }
                )
        return rows

    if data_yaml is None:
        raise ValueError("Pass --data-yaml or --dataset-manifest")
    yaml_payload = parse_simple_yaml(data_yaml)
    dataset_root = data_yaml.parent / str(yaml_payload.get("path") or ".")
    split = str(yaml_payload.get("train") or "images/train")
    labels_dir = (dataset_root / split.replace("images", "labels", 1)).resolve()
    rows = []
    for label_path in sorted(labels_dir.glob("*.txt")):
        if not label_path.read_text(encoding="utf-8").strip():
            continue
        image_path = image_for_label_path(label_path)
        if image_path is None:
            continue
        rows.append(
            {
                "positive_id": label_path.stem,
                "image_path": str(image_path),
                "label_path": str(label_path),
                "class_name": "active_panel",
                "split": Path(split).name,
            }
        )
    return rows


def read_image_size(image_path: Path) -> tuple[int, int]:
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in runtime envs only
        raise RuntimeError("OpenCV/cv2 is required for real positive eval image dimensions") from exc
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image dimensions for {image_path}")
    height, width = image.shape[:2]
    return int(width), int(height)


def parse_yolo_label_boxes(label_path: Path, *, image_width: int, image_height: int) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = raw_line.split()
        if len(parts) != 5:
            continue
        try:
            class_index = int(float(parts[0]))
            cx, cy, width, height = [float(v) for v in parts[1:]]
        except ValueError:
            continue
        values = [cx, cy, width, height]
        if not all(math.isfinite(v) for v in values):
            continue
        if width <= 0 or height <= 0:
            continue
        x1 = (cx - width / 2.0) * image_width
        y1 = (cy - height / 2.0) * image_height
        x2 = (cx + width / 2.0) * image_width
        y2 = (cy + height / 2.0) * image_height
        x1 = max(0.0, min(float(image_width), x1))
        y1 = max(0.0, min(float(image_height), y1))
        x2 = max(0.0, min(float(image_width), x2))
        y2 = max(0.0, min(float(image_height), y2))
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append({"label_index": len(boxes), "line_number": line_number, "class_index": class_index, "box": [x1, y1, x2, y2]})
    return boxes


def normalize_detection(detection: dict[str, Any], *, confidence: float) -> Optional[dict[str, Any]]:
    score = float(detection.get("confidence", 0.0))
    if not math.isfinite(score) or score < confidence:
        return None
    box = detection.get("box")
    if not isinstance(box, list) or len(box) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in box]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in [x1, y1, x2, y2]) or x2 <= x1 or y2 <= y1:
        return None
    return {
        "confidence": score,
        "class_name": detection.get("class_name"),
        "class_index": detection.get("class_index"),
        "box": [x1, y1, x2, y2],
    }


def box_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    if intersection <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def evaluate_detector_positives(
    *,
    data_yaml: Optional[Path],
    dataset_manifest: Optional[Path],
    model_path: Path,
    output_path: Path,
    confidence: float = 0.25,
    iou_threshold: float = 0.30,
    limit: Optional[int] = None,
    force: bool = False,
    detector_runner: Optional[DetectionRunner] = None,
    image_size_provider: Optional[ImageSizeProvider] = None,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    if confidence < 0 or confidence > 1 or not math.isfinite(confidence):
        raise ValueError("--confidence must be between 0 and 1")
    if iou_threshold < 0 or iou_threshold > 1 or not math.isfinite(iou_threshold):
        raise ValueError("--iou-threshold must be between 0 and 1")
    if limit is not None and limit < 0:
        raise ValueError("--limit must be non-negative")

    items = load_positive_items(data_yaml=data_yaml, dataset_manifest=dataset_manifest)
    if limit is not None:
        items = items[:limit]
    if not items:
        raise ValueError("No positive active_panel images found to evaluate")

    image_paths = [Path(str(item["image_path"])) for item in items]
    for image_path in image_paths:
        if not image_path.exists():
            raise FileNotFoundError(image_path)
    for item in items:
        label_path = Path(str(item["label_path"]))
        if not label_path.exists():
            raise FileNotFoundError(label_path)

    size_provider = image_size_provider or read_image_size
    runner = detector_runner or run_yolo_detector
    detections_by_image = runner(image_paths=image_paths, model_path=model_path, confidence=confidence)

    evaluated_items: list[dict[str, Any]] = []
    total_labels = 0
    matched_labels = 0
    images_with_match = 0
    images_with_any_detection = 0
    total_detections = 0

    for item in items:
        image_path = Path(str(item["image_path"]))
        label_path = Path(str(item["label_path"]))
        image_width, image_height = size_provider(image_path)
        labels = parse_yolo_label_boxes(label_path, image_width=image_width, image_height=image_height)
        detections = [det for det in (normalize_detection(d, confidence=confidence) for d in detections_by_image.get(str(image_path), [])) if det is not None]
        total_labels += len(labels)
        total_detections += len(detections)
        if detections:
            images_with_any_detection += 1

        matches: list[dict[str, Any]] = []
        used_detections: set[int] = set()
        for label in labels:
            best_iou = 0.0
            best_index: Optional[int] = None
            for det_index, detection in enumerate(detections):
                if det_index in used_detections:
                    continue
                overlap = box_iou(label["box"], detection["box"])
                if overlap > best_iou:
                    best_iou = overlap
                    best_index = det_index
            if best_index is not None and best_iou >= iou_threshold:
                used_detections.add(best_index)
                matched_labels += 1
                matches.append(
                    {
                        "label_index": label["label_index"],
                        "detection_index": best_index,
                        "iou": best_iou,
                        "confidence": detections[best_index]["confidence"],
                    }
                )
        if matches:
            images_with_match += 1

        evaluated_items.append(
            {
                "positive_id": item.get("positive_id"),
                "image_path": str(image_path),
                "label_path": str(label_path),
                "split": item.get("split"),
                "image_size": [image_width, image_height],
                "label_count": len(labels),
                "detection_count": len(detections),
                "matched_label_count": len(matches),
                "missed_label_count": max(0, len(labels) - len(matches)),
                "matches": matches,
                "detections": detections,
            }
        )

    dataset_manifest_path = resolve_dataset_manifest(data_yaml=data_yaml, dataset_manifest=dataset_manifest)
    report = {
        "schema_version": SCHEMA_VERSION,
        "model_path": str(model_path),
        "data_yaml": str(data_yaml) if data_yaml else None,
        "dataset_manifest": str(dataset_manifest_path) if dataset_manifest_path else None,
        "confidence": confidence,
        "iou_threshold": iou_threshold,
        "summary": {
            "positive_images": len(evaluated_items),
            "positive_labels": total_labels,
            "images_with_any_detection": images_with_any_detection,
            "images_with_match": images_with_match,
            "matched_labels": matched_labels,
            "missed_labels": max(0, total_labels - matched_labels),
            "total_detections": total_detections,
            "label_recall": matched_labels / total_labels if total_labels else 0.0,
            "image_match_rate": images_with_match / len(evaluated_items),
        },
        "items": evaluated_items,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate active_panel detector recall on reviewed positive images")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--data-yaml", type=Path)
    source.add_argument("--dataset-manifest", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.30)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate_detector_positives(
        data_yaml=args.data_yaml,
        dataset_manifest=args.dataset_manifest,
        model_path=args.model,
        output_path=args.output,
        confidence=args.confidence,
        iou_threshold=args.iou_threshold,
        limit=args.limit,
        force=args.force,
    )
    print(json.dumps({"output": str(args.output), **report["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
