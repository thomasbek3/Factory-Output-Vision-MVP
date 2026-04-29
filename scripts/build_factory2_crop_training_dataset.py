#!/usr/bin/env python3
"""Build a labeled Factory2 crop-classification dataset from review packages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory2-crop-training-dataset-v1"
REVIEW_PACKAGE_SCHEMA = "factory-crop-review-package-v1"
TARGET_MODE = "crop_classifier"
WORKER_REFERENCE_SCHEMA = "factory2-worker-reference-crops-v1"
TARGET_CLASSES = ["carried_panel", "worker_only", "static_stack"]
DEFAULT_REVIEW_PACKAGE_REPORT = Path("data/reports/factory2_crop_review_package.narrow_frozen_v2.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_crop_training_dataset.narrow_frozen_v2.json")
DEFAULT_DATASET_DIR = Path("data/datasets/factory2_crop_training_dataset_narrow_frozen_v2")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_review_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = {}
        for row in reader:
            item_id = str(row.get("item_id") or "").strip()
            if item_id:
                rows[item_id] = dict(row)
        return rows


def _split_for_group(diagnostic_id: str, track_id: int) -> str:
    digest = hashlib.sha1(f"{diagnostic_id}:{track_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "val"
    return "test"


def safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


def _copy_image(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _packaged_stem(item: dict[str, Any]) -> str:
    return str(item.get("item_id") or "crop").replace("/", "-")


def _copy_training_images(*, src: Path, dataset_dir: Path, split: str, crop_label: str, stem: str, suffix: str) -> tuple[Path, Path]:
    image_path = dataset_dir / "images" / split / crop_label / f"{stem}{suffix}"
    classification_image_path = dataset_dir / split / crop_label / f"{stem}{suffix}"
    _copy_image(src, image_path)
    _copy_image(src, classification_image_path)
    return image_path, classification_image_path


def _resolve_review_labels_csv(
    review_package_report: dict[str, Any],
    review_package_report_path: Path,
    review_labels_csv_path: Path | None,
) -> Path:
    if review_labels_csv_path is not None:
        return review_labels_csv_path
    csv_path = Path(str(review_package_report.get("review_labels_csv_path") or ""))
    if csv_path.is_absolute():
        return csv_path
    if csv_path.exists():
        return csv_path.resolve()
    return (review_package_report_path.parent / csv_path).resolve()


def _normalize_target_classes(target_classes: list[str] | None) -> list[str]:
    values = target_classes or TARGET_CLASSES
    normalized = [str(value).strip() for value in values if str(value).strip()]
    if not normalized:
        raise ValueError("At least one target class is required")
    return normalized


def build_crop_training_dataset(
    *,
    review_package_report_path: Path,
    output_report_path: Path,
    dataset_dir: Path,
    review_labels_csv_path: Path | None,
    worker_reference_report_path: Path | None = None,
    target_classes: list[str] | None = None,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if dataset_dir.exists():
        if not force:
            raise FileExistsError(dataset_dir)
        shutil.rmtree(dataset_dir)

    review_package = load_json(review_package_report_path)
    if review_package.get("schema_version") != REVIEW_PACKAGE_SCHEMA:
        raise ValueError(f"Expected {REVIEW_PACKAGE_SCHEMA} review package")

    resolved_review_csv = _resolve_review_labels_csv(review_package, review_package_report_path, review_labels_csv_path)
    review_rows = _load_review_rows(resolved_review_csv)
    package_items = [item for item in as_list(review_package.get("items")) if isinstance(item, dict)]
    active_target_classes = _normalize_target_classes(target_classes)

    items: list[dict[str, Any]] = []
    skipped_unclear_count = 0
    for package_item in package_items:
        item_id = str(package_item.get("item_id") or "")
        if item_id not in review_rows:
            raise ValueError(f"Missing review_labels row for item_id {item_id}")

        review_row = review_rows[item_id]
        crop_label = str(review_row.get("crop_label") or "").strip()
        if crop_label == "unclear" or not crop_label:
            skipped_unclear_count += 1
            continue
        if crop_label not in active_target_classes:
            raise ValueError(f"Unsupported crop_label {crop_label!r} for item_id {item_id}")

        source_image = Path(str(package_item.get("packaged_image_path") or ""))
        suffix = source_image.suffix or ".jpg"
        diagnostic_id = str(package_item.get("diagnostic_id") or "diag")
        track_id = int(package_item.get("track_id") or 0)
        split = _split_for_group(diagnostic_id, track_id)
        stem = _packaged_stem(package_item)
        image_path, classification_image_path = _copy_training_images(
            src=source_image,
            dataset_dir=dataset_dir,
            split=split,
            crop_label=crop_label,
            stem=stem,
            suffix=suffix,
        )
        items.append(
            {
                "item_id": item_id,
                "diagnostic_id": diagnostic_id,
                "track_id": track_id,
                "crop_index": int(package_item.get("crop_index") or 0),
                "dataset_bucket": package_item.get("dataset_bucket"),
                "crop_label": crop_label,
                "mask_status": review_row.get("mask_status"),
                "notes": review_row.get("notes"),
                "split": split,
                "source_image_path": str(source_image),
                "image_path": str(image_path),
                "classification_image_path": str(classification_image_path),
            }
        )

    if worker_reference_report_path is not None:
        worker_reference = load_json(worker_reference_report_path)
        if worker_reference.get("schema_version") != WORKER_REFERENCE_SCHEMA:
            raise ValueError(f"Expected {WORKER_REFERENCE_SCHEMA} worker reference report")
        for index, row in enumerate(as_list(worker_reference.get("items")), start=1):
            if not isinstance(row, dict):
                continue
            placeholder = row.get("label_placeholder") or {}
            crop_label = str(placeholder.get("crop_label") or "").strip()
            if crop_label == "unclear" or not crop_label:
                skipped_unclear_count += 1
                continue
            if crop_label not in active_target_classes:
                continue
            source_image = Path(str(row.get("exported_crop_path") or ""))
            suffix = source_image.suffix or ".jpg"
            diagnostic_id = str(row.get("diagnostic_id") or "diag")
            track_id = int(row.get("track_id") or 0)
            split = _split_for_group(diagnostic_id, track_id)
            stem = f"worker-ref-{index:06d}-{safe_stem(f'{diagnostic_id}-track-{track_id:06d}')}"
            image_path, classification_image_path = _copy_training_images(
                src=source_image,
                dataset_dir=dataset_dir,
                split=split,
                crop_label=crop_label,
                stem=stem,
                suffix=suffix,
            )
            items.append(
                {
                    "item_id": row.get("item_id") or stem,
                    "diagnostic_id": diagnostic_id,
                    "track_id": track_id,
                    "crop_index": int(row.get("crop_index") or 0),
                    "dataset_bucket": row.get("dataset_bucket"),
                    "crop_label": crop_label,
                    "mask_status": placeholder.get("mask_status"),
                    "notes": placeholder.get("notes"),
                    "split": split,
                    "source_image_path": str(source_image),
                    "image_path": str(image_path),
                    "classification_image_path": str(classification_image_path),
                }
            )

    items.sort(
        key=lambda item: (
            item["split"],
            item["crop_label"],
            item["diagnostic_id"],
            item["track_id"],
            item["crop_index"],
        )
    )

    label_counts = Counter(item["crop_label"] for item in items)
    split_counts = Counter(item["split"] for item in items)
    split_label_counts: dict[str, dict[str, int]] = {}
    for split in ["train", "val", "test"]:
        counter = Counter(item["crop_label"] for item in items if item["split"] == split)
        if counter:
            split_label_counts[split] = {label: counter[label] for label in sorted(counter)}
    missing_classes = [label for label in active_target_classes if label_counts[label] == 0]
    ready_for_training = not missing_classes and bool(items)

    report = {
        "schema_version": SCHEMA_VERSION,
        "target_mode": TARGET_MODE,
        "target_classes": active_target_classes,
        "source_review_package_report_path": str(review_package_report_path),
        "source_review_labels_csv_path": str(resolved_review_csv),
        "worker_reference_report_path": str(worker_reference_report_path) if worker_reference_report_path else None,
        "dataset_dir": str(dataset_dir),
        "integration_targets": {
            "proof_gate_module": "app/services/person_panel_gate_promotion.py",
            "crop_classifier_module": "app/services/person_panel_crop_classifier.py",
            "runtime_counter_module": "app/services/runtime_event_counter.py",
            "perception_probe_script": "scripts/analyze_person_panel_separation.py",
        },
        "split_policy": {
            "group_key": "diagnostic_id + track_id",
            "strategy": "sha1-mod-100",
            "thresholds": {"train": [0, 69], "val": [70, 84], "test": [85, 99]},
        },
        "eligible_item_count": len(items),
        "skipped_unclear_count": skipped_unclear_count,
        "label_counts": {label: label_counts[label] for label in sorted(label_counts)},
        "split_counts": {split: split_counts[split] for split in sorted(split_counts)},
        "split_label_counts": split_label_counts,
        "missing_classes": missing_classes,
        "ready_for_training": ready_for_training,
        "items": items,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a labeled Factory2 crop training dataset.")
    parser.add_argument("--review-package-report", type=Path, default=DEFAULT_REVIEW_PACKAGE_REPORT)
    parser.add_argument("--review-labels-csv", type=Path, default=None)
    parser.add_argument("--worker-reference-report", type=Path, default=None)
    parser.add_argument("--target-classes", nargs="+", default=None)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_crop_training_dataset(
        review_package_report_path=args.review_package_report,
        output_report_path=args.output_report,
        dataset_dir=args.dataset_dir,
        review_labels_csv_path=args.review_labels_csv,
        worker_reference_report_path=args.worker_reference_report,
        target_classes=args.target_classes,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
