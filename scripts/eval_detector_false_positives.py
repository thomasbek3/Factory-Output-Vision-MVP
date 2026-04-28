#!/usr/bin/env python3
"""Evaluate active_panel detector false positives on known hard-negative images.

This is intentionally lightweight: it runs inference over negative examples and
writes a receipt-style JSON report before any expensive retraining is attempted.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable, Optional

SCHEMA_VERSION = "active-panel-false-positive-eval-v1"
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

DetectionRunner = Callable[..., list[dict[str, Any]]]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse the small YOLO data.yaml shape we write without adding PyYAML."""
    payload: dict[str, Any] = {}
    names: dict[int, str] = {}
    in_names = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("names:"):
            in_names = True
            continue
        if in_names and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            try:
                names[int(key)] = value.strip().strip('"\'')
            except ValueError:
                continue
            continue
        in_names = False
        if ":" in line:
            key, value = line.split(":", 1)
            payload[key.strip()] = value.strip().strip('"\'')
    if names:
        payload["names"] = names
    return payload


def resolve_dataset_manifest(*, data_yaml: Optional[Path], dataset_manifest: Optional[Path]) -> Optional[Path]:
    if dataset_manifest is not None:
        return dataset_manifest
    if data_yaml is None:
        return None
    candidate = data_yaml.parent / "dataset_manifest.json"
    return candidate if candidate.exists() else None


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


def load_negative_items(*, data_yaml: Optional[Path], dataset_manifest: Optional[Path]) -> list[dict[str, Any]]:
    manifest_path = resolve_dataset_manifest(data_yaml=data_yaml, dataset_manifest=dataset_manifest)
    if manifest_path is not None:
        payload = load_json(manifest_path)
        if payload.get("schema_version") != "active-panel-yolo-dataset-v1":
            raise ValueError("Expected dataset manifest schema_version active-panel-yolo-dataset-v1")
        rows = []
        for item in payload.get("items") or []:
            if item.get("kind") == "hard_negative":
                rows.append(
                    {
                        "negative_id": item.get("negative_id") or Path(str(item.get("image_path"))).stem,
                        "image_path": str(item.get("image_path")),
                        "label_path": str(item.get("label_path")),
                        "reason": item.get("reason"),
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
        if label_path.read_text(encoding="utf-8").strip():
            continue
        image_path = image_for_label_path(label_path)
        if image_path is None:
            continue
        rows.append(
            {
                "negative_id": label_path.stem,
                "image_path": str(image_path),
                "label_path": str(label_path),
                "reason": None,
                "split": Path(split).name,
            }
        )
    return rows


def normalize_detection(detection: dict[str, Any], *, confidence: float) -> Optional[dict[str, Any]]:
    score = float(detection.get("confidence", 0.0))
    if not math.isfinite(score) or score < confidence:
        return None
    box = detection.get("box")
    normalized: dict[str, Any] = {
        "confidence": score,
        "class_name": detection.get("class_name"),
        "class_index": detection.get("class_index"),
    }
    if box is not None:
        normalized["box"] = box
    return normalized


def run_yolo_detector(*, image_paths: list[Path], model_path: Path, confidence: float) -> dict[str, list[dict[str, Any]]]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    output: dict[str, list[dict[str, Any]]] = {}
    for image_path in image_paths:
        results = model.predict(str(image_path), conf=confidence, verbose=False)
        detections: list[dict[str, Any]] = []
        for result in results:
            names = getattr(result, "names", {}) or getattr(model, "names", {})
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            xyxy_values = boxes.xyxy.tolist() if hasattr(boxes.xyxy, "tolist") else list(boxes.xyxy)
            conf_values = boxes.conf.tolist() if hasattr(boxes.conf, "tolist") else list(boxes.conf)
            cls_values = boxes.cls.tolist() if hasattr(boxes.cls, "tolist") else list(boxes.cls)
            for xyxy, score, cls in zip(xyxy_values, conf_values, cls_values):
                class_index = int(cls)
                detections.append(
                    {
                        "box": [float(v) for v in xyxy],
                        "confidence": float(score),
                        "class_index": class_index,
                        "class_name": names.get(class_index) if isinstance(names, dict) else None,
                    }
                )
        output[str(image_path)] = detections
    return output


def evaluate_false_positives(
    *,
    data_yaml: Optional[Path],
    dataset_manifest: Optional[Path],
    model_path: Path,
    output_path: Path,
    confidence: float = 0.25,
    limit: Optional[int] = None,
    force: bool = False,
    detector_runner: Optional[DetectionRunner] = None,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    if confidence < 0 or confidence > 1 or not math.isfinite(confidence):
        raise ValueError("--confidence must be between 0 and 1")
    if limit is not None and limit < 0:
        raise ValueError("--limit must be non-negative")

    items = load_negative_items(data_yaml=data_yaml, dataset_manifest=dataset_manifest)
    if limit is not None:
        items = items[:limit]
    if not items:
        raise ValueError("No hard-negative images found to evaluate")

    image_paths = [Path(str(item["image_path"])) for item in items]
    for image_path in image_paths:
        if not image_path.exists():
            raise FileNotFoundError(image_path)

    runner = detector_runner or run_yolo_detector
    detections_by_image = runner(image_paths=image_paths, model_path=model_path, confidence=confidence)

    evaluated_items: list[dict[str, Any]] = []
    false_positive_count = 0
    images_with_false_positives = 0
    for item in items:
        image_path = Path(str(item["image_path"]))
        raw_detections = detections_by_image.get(str(image_path), [])
        detections = [det for det in (normalize_detection(d, confidence=confidence) for d in raw_detections) if det is not None]
        if detections:
            images_with_false_positives += 1
            false_positive_count += len(detections)
        evaluated_items.append(
            {
                "negative_id": item.get("negative_id"),
                "image_path": str(image_path),
                "label_path": item.get("label_path"),
                "reason": item.get("reason"),
                "split": item.get("split"),
                "false_positive_count": len(detections),
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
        "summary": {
            "hard_negative_images": len(evaluated_items),
            "images_with_false_positives": images_with_false_positives,
            "false_positive_detections": false_positive_count,
            "false_positive_image_rate": images_with_false_positives / len(evaluated_items),
        },
        "items": evaluated_items,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate detector false positives on active_panel hard negatives")
    parser.add_argument("--data-yaml", type=Path, default=Path("data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml"))
    parser.add_argument("--dataset-manifest", type=Path, default=None)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_false_positives(
        data_yaml=args.data_yaml,
        dataset_manifest=args.dataset_manifest,
        model_path=args.model,
        output_path=args.output,
        confidence=args.confidence,
        limit=args.limit,
        force=args.force,
    )
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
