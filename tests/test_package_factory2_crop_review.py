from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import package_factory2_crop_review as review_package


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_image(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_package_crop_review_writes_ranked_manifest_csv_and_images(tmp_path: Path) -> None:
    blocked_crop = _write_image(tmp_path / "dataset" / "blocked-01.jpg", b"blocked")
    accepted_crop = _write_image(tmp_path / "dataset" / "accepted-01.jpg", b"accepted")
    dataset_report = _write_json(
        tmp_path / "blocked_crop_dataset.json",
        {
            "schema_version": "factory-blocked-crop-dataset-v1",
            "items": [
                {
                    "dataset_bucket": "blocked_worker_overlap",
                    "diagnostic_id": "factory2-review-0002-222s-panel-v1",
                    "diagnostic_path": "diag/review-0002/diagnostic.json",
                    "track_id": 2,
                    "crop_index": 1,
                    "timestamp_seconds": 204.717,
                    "zone": "source",
                    "gate_decision": "reject",
                    "gate_reason": "worker_body_overlap",
                    "failure_link": "worker_body_overlap",
                    "worker_overlap_detail": "fully_entangled_with_worker",
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 0.0,
                    "person_panel_recommendation": "countable_panel_candidate",
                    "person_panel_separation_decision": "separable_panel_candidate",
                    "receipt_json_path": "diag/review-0002/track-000002.json",
                    "receipt_card_path": "diag/review-0002/track-000002-sheet.jpg",
                    "receipt_timestamps": {"first": 204.717, "last": 210.384},
                    "exported_crop_path": str(blocked_crop),
                    "label_placeholder": {"crop_label": "unclear", "mask_status": "missing", "notes": ""},
                    "window": {"start_timestamp": 202.384, "end_timestamp": 242.384, "fps": 3.0},
                },
                {
                    "dataset_bucket": "accepted_positive_boundary",
                    "diagnostic_id": "factory2-review-0011-372-412s-panel-v1-5fps",
                    "diagnostic_path": "diag/review-0011/diagnostic.json",
                    "track_id": 2,
                    "crop_index": 1,
                    "timestamp_seconds": 387.3,
                    "zone": "source",
                    "gate_decision": "allow_source_token",
                    "gate_reason": "moving_panel_candidate",
                    "failure_link": "source_token_approved",
                    "worker_overlap_detail": "fully_entangled_with_worker",
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 0.0,
                    "person_panel_recommendation": "countable_panel_candidate",
                    "person_panel_separation_decision": "separable_panel_candidate",
                    "receipt_json_path": "diag/review-0011/track-000002.json",
                    "receipt_card_path": "diag/review-0011/track-000002-sheet.jpg",
                    "receipt_timestamps": {"first": 387.3, "last": 402.1},
                    "exported_crop_path": str(accepted_crop),
                    "label_placeholder": {"crop_label": "carried_panel", "mask_status": "missing", "notes": ""},
                    "window": {"start_timestamp": 372.0, "end_timestamp": 412.0, "fps": 5.0},
                },
            ],
        },
    )
    output_report = tmp_path / "out" / "review_package.json"
    package_dir = tmp_path / "out" / "package"

    result = review_package.package_crop_review(
        crop_dataset_report_path=dataset_report,
        output_report_path=output_report,
        package_dir=package_dir,
        force=False,
    )

    assert result["schema_version"] == "factory-crop-review-package-v1"
    assert result["item_count"] == 2
    assert result["priority_counts"] == {
        "p0_candidate_salvage": 1,
        "p3_positive_boundary": 1,
    }
    assert result["items"][0]["review_priority"] == "p0_candidate_salvage"
    assert result["items"][1]["review_priority"] == "p3_positive_boundary"
    assert Path(result["items"][0]["packaged_image_path"]).read_bytes() == b"blocked"
    assert Path(result["items"][1]["packaged_image_path"]).read_bytes() == b"accepted"
    assert result["items"][0]["label_placeholder"]["crop_label"] == "unclear"
    assert result["items"][1]["label_placeholder"]["crop_label"] == "carried_panel"
    assert result["items"][0]["review_focus"] == "verify whether this blocked crop is a real carried panel"
    assert result["items"][1]["review_focus"] == "retain as positive boundary reference for carried panel appearance"
    assert json.loads(output_report.read_text(encoding="utf-8")) == result

    csv_rows = list(csv.DictReader((package_dir / "review_labels.csv").read_text(encoding="utf-8").splitlines()))
    assert [row["item_id"] for row in csv_rows] == [result["items"][0]["item_id"], result["items"][1]["item_id"]]
    assert csv_rows[0]["crop_label"] == "unclear"
    assert csv_rows[1]["crop_label"] == "carried_panel"
    assert (package_dir / "classes.txt").read_text(encoding="utf-8").splitlines() == [
        "carried_panel",
        "worker_only",
        "static_stack",
        "unclear",
    ]
    assert "Roboflow-safe flat image directory" in (package_dir / "README.md").read_text(encoding="utf-8")


def test_package_crop_review_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    image = _write_image(tmp_path / "dataset" / "blocked.jpg", b"x")
    dataset_report = _write_json(
        tmp_path / "blocked_crop_dataset.json",
        {
            "schema_version": "factory-blocked-crop-dataset-v1",
            "items": [
                {
                    "dataset_bucket": "blocked_worker_overlap",
                    "diagnostic_id": "diag",
                    "diagnostic_path": "diag/diagnostic.json",
                    "track_id": 1,
                    "crop_index": 1,
                    "timestamp_seconds": 1.0,
                    "zone": "source",
                    "gate_decision": "reject",
                    "gate_reason": "worker_body_overlap",
                    "failure_link": "worker_body_overlap",
                    "worker_overlap_detail": "fully_entangled_with_worker",
                    "person_panel_recommendation": "not_panel",
                    "person_panel_separation_decision": "worker_body_overlap",
                    "exported_crop_path": str(image),
                    "label_placeholder": {"crop_label": "unclear", "mask_status": "missing", "notes": ""},
                }
            ],
        },
    )
    output_report = tmp_path / "out" / "review_package.json"
    package_dir = tmp_path / "out" / "package"

    review_package.package_crop_review(
        crop_dataset_report_path=dataset_report,
        output_report_path=output_report,
        package_dir=package_dir,
        force=False,
    )

    with pytest.raises(FileExistsError):
        review_package.package_crop_review(
            crop_dataset_report_path=dataset_report,
            output_report_path=output_report,
            package_dir=package_dir,
            force=False,
        )
