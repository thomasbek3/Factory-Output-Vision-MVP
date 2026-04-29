from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image

from scripts import export_factory2_worker_reference_crops as exporter


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_review_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item_id", "crop_label", "mask_status", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_frame(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (100, 80), color).save(path)
    return path


def test_export_worker_reference_crops_samples_nearby_nontrack_person_crop(tmp_path: Path) -> None:
    diag_dir = tmp_path / "diag"
    frames_dir = diag_dir / "frames"
    frame_003 = _write_frame(frames_dir / "frame_000003.jpg", (10, 20, 30))
    _write_frame(frames_dir / "frame_000004.jpg", (40, 50, 60))
    frame_005 = _write_frame(frames_dir / "frame_000005.jpg", (70, 80, 90))

    receipt_json = _write_json(
        diag_dir / "track_receipts" / "track-000005.json",
        {
            "track_id": 5,
            "evidence": {
                "observations": [
                    {
                        "frame_path": str(frame_005),
                        "timestamp": 10.0,
                        "zone": "source",
                    }
                ]
            },
        },
    )
    _write_json(
        diag_dir / "track_receipts" / "track-000005-person-panel-separation.json",
        {
            "track_id": 5,
            "selected_frames": [
                {
                    "frame_path": str(frame_005),
                    "timestamp": 10.0,
                    "zone": "source",
                    "person_box_xywh": [50.0, 40.0, 40.0, 60.0],
                    "panel_box_xywh": [60.0, 45.0, 20.0, 20.0],
                }
            ],
        },
    )

    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {"item_id": "diag-track-000005-crop-01", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-track-000005-crop-02", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
        ],
    )
    package_report = _write_json(
        tmp_path / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "diag-track-000005-crop-01",
                    "diagnostic_id": "diag",
                    "track_id": 5,
                    "crop_index": 1,
                    "dataset_bucket": "accepted_positive_boundary",
                    "receipt_json_path": str(receipt_json),
                },
                {
                    "item_id": "diag-track-000005-crop-02",
                    "diagnostic_id": "diag",
                    "track_id": 5,
                    "crop_index": 2,
                    "dataset_bucket": "blocked_worker_overlap",
                    "receipt_json_path": str(receipt_json),
                },
            ],
        },
    )

    output_report = tmp_path / "out" / "worker_refs.json"
    dataset_dir = tmp_path / "out" / "dataset"

    result = exporter.export_worker_reference_crops(
        review_package_report_path=package_report,
        review_labels_csv_path=None,
        output_report_path=output_report,
        dataset_dir=dataset_dir,
        force=False,
    )

    assert result["schema_version"] == "factory2-worker-reference-crops-v1"
    assert result["candidate_count"] == 1
    item = result["items"][0]
    assert item["dataset_bucket"] == "reference_worker_only_candidate"
    assert item["label_placeholder"]["crop_label"] == "worker_only"
    assert item["sampled_frame_path"] == str(frame_003)
    exported_crop = Path(item["exported_crop_path"])
    assert exported_crop.exists()
    assert Image.open(exported_crop).size == (40, 60)
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_export_worker_reference_crops_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    diag_dir = tmp_path / "diag"
    frame_003 = _write_frame(diag_dir / "frames" / "frame_000003.jpg", (10, 20, 30))
    receipt_json = _write_json(
        diag_dir / "track_receipts" / "track-000001.json",
        {"track_id": 1, "evidence": {"observations": []}},
    )
    _write_json(
        diag_dir / "track_receipts" / "track-000001-person-panel-separation.json",
        {
            "track_id": 1,
            "selected_frames": [
                {
                    "frame_path": str(frame_003),
                    "timestamp": 3.0,
                    "person_box_xywh": [50.0, 40.0, 20.0, 20.0],
                }
            ],
        },
    )
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [{"item_id": "diag-track-000001-crop-01", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""}],
    )
    package_report = _write_json(
        tmp_path / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "diag-track-000001-crop-01",
                    "diagnostic_id": "diag",
                    "track_id": 1,
                    "crop_index": 1,
                    "dataset_bucket": "accepted_positive_boundary",
                    "receipt_json_path": str(receipt_json),
                }
            ],
        },
    )

    exporter.export_worker_reference_crops(
        review_package_report_path=package_report,
        review_labels_csv_path=None,
        output_report_path=tmp_path / "out" / "worker_refs.json",
        dataset_dir=tmp_path / "out" / "dataset",
        force=False,
    )

    try:
        exporter.export_worker_reference_crops(
            review_package_report_path=package_report,
            review_labels_csv_path=None,
            output_report_path=tmp_path / "out" / "worker_refs.json",
            dataset_dir=tmp_path / "out" / "dataset",
            force=False,
        )
    except FileExistsError:
        return
    raise AssertionError("expected FileExistsError")


def test_export_worker_reference_crops_samples_outside_selected_frame_span(tmp_path: Path) -> None:
    diag_dir = tmp_path / "diag"
    frames_dir = diag_dir / "frames"
    for idx in range(1, 9):
        _write_frame(frames_dir / f"frame_{idx:06d}.jpg", (idx, idx, idx))

    receipt_json = _write_json(
        diag_dir / "track_receipts" / "track-000002.json",
        {
            "track_id": 2,
            "evidence": {
                "observations": [
                    {"frame_path": str(frames_dir / "frame_000003.jpg"), "timestamp": 3.0},
                    {"frame_path": str(frames_dir / "frame_000006.jpg"), "timestamp": 6.0},
                ]
            },
        },
    )
    _write_json(
        diag_dir / "track_receipts" / "track-000002-person-panel-separation.json",
        {
            "track_id": 2,
            "selected_frames": [
                {"frame_path": str(frames_dir / "frame_000003.jpg"), "person_box_xywh": [30.0, 30.0, 20.0, 20.0]},
                {"frame_path": str(frames_dir / "frame_000006.jpg"), "person_box_xywh": [30.0, 30.0, 20.0, 20.0]},
            ],
        },
    )
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [{"item_id": "diag-track-000002-crop-01", "crop_label": "carried_panel", "mask_status": "missing", "notes": ""}],
    )
    package_report = _write_json(
        tmp_path / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "diag-track-000002-crop-01",
                    "diagnostic_id": "diag",
                    "track_id": 2,
                    "crop_index": 1,
                    "dataset_bucket": "accepted_positive_boundary",
                    "receipt_json_path": str(receipt_json),
                }
            ],
        },
    )

    result = exporter.export_worker_reference_crops(
        review_package_report_path=package_report,
        review_labels_csv_path=None,
        output_report_path=tmp_path / "out" / "worker_refs.json",
        dataset_dir=tmp_path / "out" / "dataset",
        force=False,
    )

    assert result["items"][0]["sampled_frame_path"] == str(frames_dir / "frame_000001.jpg")
