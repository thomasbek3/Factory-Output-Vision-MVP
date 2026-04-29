from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import build_factory2_crop_training_dataset as builder


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_image(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _write_review_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "crop_label",
                "mask_status",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_build_crop_training_dataset_uses_review_labels_and_groups_tracks(tmp_path: Path) -> None:
    panel_a = _write_image(tmp_path / "package" / "images" / "panel-a.jpg", b"panel-a")
    panel_b = _write_image(tmp_path / "package" / "images" / "panel-b.jpg", b"panel-b")
    worker = _write_image(tmp_path / "package" / "images" / "worker.jpg", b"worker")
    unclear = _write_image(tmp_path / "package" / "images" / "unclear.jpg", b"unclear")
    review_csv = _write_review_csv(
        tmp_path / "package" / "review_labels.csv",
        [
            {"item_id": "diag-a-track-000005-crop-01", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-a-track-000005-crop-02", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-b-track-000007-crop-01", "crop_label": "worker_only", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-c-track-000009-crop-01", "crop_label": "unclear", "mask_status": "missing", "notes": ""},
        ],
    )
    package_report = _write_json(
        tmp_path / "package" / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "diag-a-track-000005-crop-01",
                    "diagnostic_id": "diag-a",
                    "track_id": 5,
                    "crop_index": 1,
                    "dataset_bucket": "accepted_positive_boundary",
                    "packaged_image_path": str(panel_a),
                    "label_placeholder": {"crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
                },
                {
                    "item_id": "diag-a-track-000005-crop-02",
                    "diagnostic_id": "diag-a",
                    "track_id": 5,
                    "crop_index": 2,
                    "dataset_bucket": "accepted_positive_boundary",
                    "packaged_image_path": str(panel_b),
                    "label_placeholder": {"crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
                },
                {
                    "item_id": "diag-b-track-000007-crop-01",
                    "diagnostic_id": "diag-b",
                    "track_id": 7,
                    "crop_index": 1,
                    "dataset_bucket": "blocked_worker_overlap",
                    "packaged_image_path": str(worker),
                    "label_placeholder": {"crop_label": "unclear", "mask_status": "missing", "notes": ""},
                },
                {
                    "item_id": "diag-c-track-000009-crop-01",
                    "diagnostic_id": "diag-c",
                    "track_id": 9,
                    "crop_index": 1,
                    "dataset_bucket": "blocked_worker_overlap",
                    "packaged_image_path": str(unclear),
                    "label_placeholder": {"crop_label": "unclear", "mask_status": "missing", "notes": ""},
                },
            ],
        },
    )
    output_report = tmp_path / "out" / "crop_training_dataset.json"
    out_dir = tmp_path / "out" / "dataset"

    result = builder.build_crop_training_dataset(
        review_package_report_path=package_report,
        output_report_path=output_report,
        dataset_dir=out_dir,
        review_labels_csv_path=None,
        force=False,
    )

    assert result["schema_version"] == "factory2-crop-training-dataset-v1"
    assert result["target_mode"] == "crop_classifier"
    assert result["eligible_item_count"] == 3
    assert result["skipped_unclear_count"] == 1
    assert result["label_counts"] == {"carried_panel": 2, "worker_only": 1}
    assert result["missing_classes"] == ["static_stack"]
    assert result["ready_for_training"] is False
    assert len(result["items"]) == 3
    assert result["items"][0]["crop_label"] == "carried_panel"
    assert result["items"][2]["crop_label"] == "worker_only"
    assert result["items"][0]["split"] == result["items"][1]["split"]
    assert Path(result["items"][0]["image_path"]).read_bytes() == b"panel-a"
    assert Path(result["items"][1]["image_path"]).read_bytes() == b"panel-b"
    assert Path(result["items"][2]["image_path"]).read_bytes() == b"worker"
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_build_crop_training_dataset_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    image = _write_image(tmp_path / "package" / "images" / "panel.jpg", b"panel")
    review_csv = _write_review_csv(
        tmp_path / "package" / "review_labels.csv",
        [{"item_id": "diag-a-track-000005-crop-01", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""}],
    )
    package_report = _write_json(
        tmp_path / "package" / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "diag-a-track-000005-crop-01",
                    "diagnostic_id": "diag-a",
                    "track_id": 5,
                    "crop_index": 1,
                    "dataset_bucket": "accepted_positive_boundary",
                    "packaged_image_path": str(image),
                    "label_placeholder": {"crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
                }
            ],
        },
    )
    output_report = tmp_path / "out" / "crop_training_dataset.json"
    out_dir = tmp_path / "out" / "dataset"

    builder.build_crop_training_dataset(
        review_package_report_path=package_report,
        output_report_path=output_report,
        dataset_dir=out_dir,
        review_labels_csv_path=None,
        force=False,
    )

    with pytest.raises(FileExistsError):
        builder.build_crop_training_dataset(
            review_package_report_path=package_report,
            output_report_path=output_report,
            dataset_dir=out_dir,
            review_labels_csv_path=None,
            force=False,
        )
