#!/usr/bin/env python3
"""Build a labeled relation-classification dataset for Factory2's final two divergent events."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory2-final-two-rescue-dataset-v1"
REVIEW_SCHEMA = "factory2-divergent-chain-review-v1"
TARGET_MODE = "relation_classifier"
TARGET_RELATION_CLASSES = ["distinct_new_delivery", "same_delivery_as_prior", "static_resident"]
STATIC_REFERENCE_SCHEMA = "factory2-static-resident-reference-crops-v1"
DEFAULT_REVIEW_REPORT = Path("data/reports/factory2_divergent_chain_review.v1.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_final_two_rescue_dataset.v1.json")
DEFAULT_DATASET_DIR = Path("data/datasets/factory2_final_two_rescue_dataset_v1")


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


def _split_for_group(event_id: str, track_id: int) -> str:
    digest = hashlib.sha1(f"{event_id}:{track_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "val"
    return "test"


def _copy_image(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _resolve_review_labels_csv(
    review_report: dict[str, Any],
    review_report_path: Path,
    review_labels_csv_path: Path | None,
) -> Path:
    if review_labels_csv_path is not None:
        return review_labels_csv_path
    csv_path = Path(str(review_report.get("review_labels_csv_path") or ""))
    if csv_path.is_absolute():
        return csv_path
    if csv_path.exists():
        return csv_path.resolve()
    return (review_report_path.parent / csv_path).resolve()


def build_final_two_rescue_dataset(
    *,
    review_report_path: Path,
    output_report_path: Path,
    dataset_dir: Path,
    review_labels_csv_path: Path | None,
    static_reference_report_path: Path | None = None,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if dataset_dir.exists():
        if not force:
            raise FileExistsError(dataset_dir)
        shutil.rmtree(dataset_dir)

    review_report = load_json(review_report_path)
    if review_report.get("schema_version") != REVIEW_SCHEMA:
        raise ValueError(f"Expected {REVIEW_SCHEMA} review report")

    resolved_review_csv = _resolve_review_labels_csv(review_report, review_report_path, review_labels_csv_path)
    review_rows = _load_review_rows(resolved_review_csv)
    package_items = [item for item in as_list(review_report.get("items")) if isinstance(item, dict)]

    items: list[dict[str, Any]] = []
    skipped_unclear_relation_count = 0
    for review_item in package_items:
        item_id = str(review_item.get("item_id") or "")
        if item_id not in review_rows:
            raise ValueError(f"Missing review_labels row for item_id {item_id}")
        review_row = review_rows[item_id]
        crop_label = str(review_row.get("crop_label") or "").strip()
        relation_label = str(review_row.get("relation_label") or "").strip()
        if crop_label != "carried_panel":
            continue
        if relation_label == "unclear" or not relation_label:
            skipped_unclear_relation_count += 1
            continue
        if relation_label not in TARGET_RELATION_CLASSES:
            raise ValueError(f"Unsupported relation_label {relation_label!r} for item_id {item_id}")

        source_image = Path(str(review_item.get("crop_image_path") or ""))
        suffix = source_image.suffix or ".jpg"
        event_id = str(review_item.get("event_id") or "event")
        track_id = int(review_item.get("track_id") or 0)
        split = _split_for_group(event_id, track_id)
        stem = item_id.replace("/", "-")
        image_path = dataset_dir / "images" / split / relation_label / f"{stem}{suffix}"
        classification_image_path = dataset_dir / split / relation_label / f"{stem}{suffix}"
        _copy_image(source_image, image_path)
        _copy_image(source_image, classification_image_path)
        items.append(
            {
                "item_id": item_id,
                "event_id": event_id,
                "track_id": track_id,
                "track_role": review_item.get("track_role"),
                "track_class": review_item.get("track_class"),
                "crop_label": crop_label,
                "relation_label": relation_label,
                "notes": review_row.get("notes"),
                "split": split,
                "source_image_path": str(source_image),
                "image_path": str(image_path),
                "classification_image_path": str(classification_image_path),
            }
        )

    if static_reference_report_path is not None:
        static_reference_report = load_json(static_reference_report_path)
        if static_reference_report.get("schema_version") != STATIC_REFERENCE_SCHEMA:
            raise ValueError(f"Expected {STATIC_REFERENCE_SCHEMA} static reference report")
        for row in as_list(static_reference_report.get("items")):
            if not isinstance(row, dict):
                continue
            placeholder = row.get("label_placeholder") or {}
            crop_label = str(placeholder.get("crop_label") or "").strip()
            relation_label = str(placeholder.get("relation_label") or "").strip()
            if crop_label != "carried_panel":
                continue
            if relation_label not in TARGET_RELATION_CLASSES:
                continue
            source_image = Path(str(row.get("exported_crop_path") or ""))
            suffix = source_image.suffix or ".jpg"
            event_id = str(row.get("event_id") or "static-resident-reference")
            track_id = int(row.get("track_id") or 0)
            split = _split_for_group(event_id, track_id)
            item_id = str(row.get("item_id") or f"static-ref-track-{track_id:06d}")
            stem = item_id.replace("/", "-")
            image_path = dataset_dir / "images" / split / relation_label / f"{stem}{suffix}"
            classification_image_path = dataset_dir / split / relation_label / f"{stem}{suffix}"
            _copy_image(source_image, image_path)
            _copy_image(source_image, classification_image_path)
            items.append(
                {
                    "item_id": item_id,
                    "event_id": event_id,
                    "track_id": track_id,
                    "track_role": row.get("track_role"),
                    "track_class": row.get("track_class"),
                    "crop_label": crop_label,
                    "relation_label": relation_label,
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
            item["relation_label"],
            item["event_id"],
            item["track_id"],
            item["item_id"],
        )
    )

    crop_label_counts = Counter(item["crop_label"] for item in items)
    relation_label_counts = Counter(item["relation_label"] for item in items)
    split_counts = Counter(item["split"] for item in items)
    split_relation_counts: dict[str, dict[str, int]] = {}
    for split in ["train", "val", "test"]:
        counter = Counter(item["relation_label"] for item in items if item["split"] == split)
        if counter:
            split_relation_counts[split] = {label: counter[label] for label in sorted(counter)}
    missing_relation_classes = [label for label in TARGET_RELATION_CLASSES if relation_label_counts[label] == 0]
    ready_for_training = not missing_relation_classes and bool(items)

    report = {
        "schema_version": SCHEMA_VERSION,
        "target_mode": TARGET_MODE,
        "target_relation_classes": TARGET_RELATION_CLASSES,
        "source_review_report_path": str(review_report_path),
        "source_review_labels_csv_path": str(resolved_review_csv),
        "static_reference_report_path": str(static_reference_report_path) if static_reference_report_path else None,
        "dataset_dir": str(dataset_dir),
        "split_policy": {
            "group_key": "event_id + track_id",
            "strategy": "sha1-mod-100",
            "thresholds": {"train": [0, 69], "val": [70, 84], "test": [85, 99]},
        },
        "eligible_item_count": len(items),
        "skipped_unclear_relation_count": skipped_unclear_relation_count,
        "crop_label_counts": {label: crop_label_counts[label] for label in sorted(crop_label_counts)},
        "relation_label_counts": {label: relation_label_counts[label] for label in sorted(relation_label_counts)},
        "split_counts": {split: split_counts[split] for split in sorted(split_counts)},
        "split_relation_counts": split_relation_counts,
        "missing_relation_classes": missing_relation_classes,
        "ready_for_training": ready_for_training,
        "items": items,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a final-two rescue dataset from divergent chain labels.")
    parser.add_argument("--review-report", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--review-labels-csv", type=Path, default=None)
    parser.add_argument("--static-reference-report", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_final_two_rescue_dataset(
        review_report_path=args.review_report,
        output_report_path=args.output_report,
        dataset_dir=args.dataset_dir,
        review_labels_csv_path=args.review_labels_csv,
        static_reference_report_path=args.static_reference_report,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
