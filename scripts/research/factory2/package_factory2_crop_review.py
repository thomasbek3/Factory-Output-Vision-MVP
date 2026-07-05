#!/usr/bin/env python3
"""Package Factory2 crop exports into a label-ready review bundle."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-crop-review-package-v1"
DEFAULT_DATASET_REPORT = Path("data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_crop_review_package.narrow_frozen_v2.json")
DEFAULT_PACKAGE_DIR = Path("data/datasets/factory2_crop_review_package_narrow_frozen_v2")
CROP_LABELS = ["carried_panel", "worker_only", "static_stack", "unclear"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _priority_for_item(item: dict[str, Any]) -> tuple[int, str, str]:
    bucket = str(item.get("dataset_bucket") or "")
    recommendation = str(item.get("person_panel_recommendation") or "")
    if bucket == "blocked_worker_overlap" and recommendation == "countable_panel_candidate":
        return (0, "p0_candidate_salvage", "verify whether this blocked crop is a real carried panel")
    if bucket == "blocked_worker_overlap" and recommendation == "insufficient_visibility":
        return (1, "p1_visibility_review", "decide whether better masks or more context could rescue this crop")
    if bucket == "blocked_worker_overlap":
        return (2, "p2_negative_confirmation", "confirm this blocked crop is worker/body/static stack rather than carried panel")
    return (3, "p3_positive_boundary", "retain as positive boundary reference for carried panel appearance")


def _item_id(item: dict[str, Any]) -> str:
    diagnostic_id = str(item.get("diagnostic_id") or "diag")
    track_id = int(item.get("track_id") or 0)
    crop_index = int(item.get("crop_index") or 0)
    return f"{diagnostic_id}-track-{track_id:06d}-crop-{crop_index:02d}"


def _copy_packaged_image(src: Path, package_dir: Path, item_id: str) -> Path:
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    destination = images_dir / f"{item_id}{src.suffix or '.jpg'}"
    shutil.copy2(src, destination)
    return destination


def _write_classes(path: Path) -> None:
    path.write_text("\n".join(CROP_LABELS) + "\n", encoding="utf-8")


def _write_readme(path: Path) -> None:
    path.write_text(
        "# Factory2 Crop Review Package\n\n"
        "This package is for local review or later private Roboflow upload.\n\n"
        "- `images/` is a Roboflow-safe flat image directory.\n"
        "- `review_manifest.json` preserves the full provenance for every crop.\n"
        "- `review_labels.csv` is the writable label sheet.\n"
        "- `classes.txt` lists the target crop labels.\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "item_id",
        "review_priority",
        "dataset_bucket",
        "packaged_image_path",
        "diagnostic_id",
        "track_id",
        "crop_index",
        "timestamp_seconds",
        "zone",
        "gate_decision",
        "gate_reason",
        "failure_link",
        "worker_overlap_detail",
        "person_panel_recommendation",
        "person_panel_separation_decision",
        "crop_label",
        "mask_status",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            placeholder = item.get("label_placeholder") or {}
            writer.writerow(
                {
                    "item_id": item.get("item_id"),
                    "review_priority": item.get("review_priority"),
                    "dataset_bucket": item.get("dataset_bucket"),
                    "packaged_image_path": item.get("packaged_image_path"),
                    "diagnostic_id": item.get("diagnostic_id"),
                    "track_id": item.get("track_id"),
                    "crop_index": item.get("crop_index"),
                    "timestamp_seconds": item.get("timestamp_seconds"),
                    "zone": item.get("zone"),
                    "gate_decision": item.get("gate_decision"),
                    "gate_reason": item.get("gate_reason"),
                    "failure_link": item.get("failure_link"),
                    "worker_overlap_detail": item.get("worker_overlap_detail"),
                    "person_panel_recommendation": item.get("person_panel_recommendation"),
                    "person_panel_separation_decision": item.get("person_panel_separation_decision"),
                    "crop_label": placeholder.get("crop_label"),
                    "mask_status": placeholder.get("mask_status"),
                    "notes": placeholder.get("notes"),
                }
            )


def package_crop_review(
    *,
    crop_dataset_report_path: Path,
    output_report_path: Path,
    package_dir: Path,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if package_dir.exists():
        if not force:
            raise FileExistsError(package_dir)
        shutil.rmtree(package_dir)

    dataset = load_json(crop_dataset_report_path)
    source_items = [item for item in as_list(dataset.get("items")) if isinstance(item, dict)]
    enriched: list[dict[str, Any]] = []
    for row in source_items:
        exported_crop = Path(str(row.get("exported_crop_path") or ""))
        if not exported_crop.exists():
            continue
        priority_rank, review_priority, review_focus = _priority_for_item(row)
        item_id = _item_id(row)
        packaged = _copy_packaged_image(exported_crop, package_dir, item_id)
        enriched.append(
            {
                **row,
                "item_id": item_id,
                "priority_rank": priority_rank,
                "review_priority": review_priority,
                "review_focus": review_focus,
                "packaged_image_path": str(packaged),
            }
        )

    enriched.sort(
        key=lambda item: (
            int(item.get("priority_rank") or 0),
            str(item.get("diagnostic_id") or ""),
            int(item.get("track_id") or 0),
            int(item.get("crop_index") or 0),
        )
    )

    review_manifest_path = package_dir / "review_manifest.json"
    review_labels_csv_path = package_dir / "review_labels.csv"
    classes_path = package_dir / "classes.txt"
    readme_path = package_dir / "README.md"
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(review_labels_csv_path, enriched)
    _write_classes(classes_path)
    _write_readme(readme_path)

    priority_counts = Counter(str(item.get("review_priority") or "unknown") for item in enriched)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset_report_path": str(crop_dataset_report_path),
        "package_dir": str(package_dir),
        "review_manifest_path": str(review_manifest_path),
        "review_labels_csv_path": str(review_labels_csv_path),
        "classes_path": str(classes_path),
        "item_count": len(enriched),
        "priority_counts": {key: priority_counts[key] for key in sorted(priority_counts)},
        "items": enriched,
    }
    review_manifest_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package Factory2 crop review artifacts for labeling.")
    parser.add_argument("--crop-dataset-report", type=Path, default=DEFAULT_DATASET_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = package_crop_review(
        crop_dataset_report_path=args.crop_dataset_report,
        output_report_path=args.output_report,
        package_dir=args.package_dir,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
