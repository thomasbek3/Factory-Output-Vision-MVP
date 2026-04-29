from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import apply_factory2_track_review_labels as applier


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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


def test_apply_track_review_labels_updates_matching_rows_and_preserves_unmatched(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {"item_id": "diag-a-track-000005-crop-01", "crop_label": "unclear", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-a-track-000005-crop-02", "crop_label": "unclear", "mask_status": "missing", "notes": ""},
            {"item_id": "diag-b-track-000007-crop-01", "crop_label": "unclear", "mask_status": "missing", "notes": ""},
        ],
    )
    package_report = _write_json(
        tmp_path / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {"item_id": "diag-a-track-000005-crop-01", "diagnostic_id": "diag-a", "track_id": 5},
                {"item_id": "diag-a-track-000005-crop-02", "diagnostic_id": "diag-a", "track_id": 5},
                {"item_id": "diag-b-track-000007-crop-01", "diagnostic_id": "diag-b", "track_id": 7},
            ],
        },
    )
    oracle_labels = _write_json(
        tmp_path / "oracle_labels.json",
        {
            "diag-a|5": {
                "crop_label": "carried_panel",
                "confidence": "high",
                "short_reason": "Visible wire mesh panel spans the sequence.",
            },
            "diag-b|7": {
                "crop_label": "worker_only",
                "confidence": "medium",
                "short_reason": "Worker silhouette without discrete panel edge.",
            },
        },
    )
    output_csv = tmp_path / "applied.csv"

    result = applier.apply_track_review_labels(
        review_package_report_path=package_report,
        oracle_labels_json_path=oracle_labels,
        output_csv_path=output_csv,
        input_csv_path=None,
        force=False,
    )

    assert result["schema_version"] == "factory2-track-review-application-v1"
    assert result["updated_row_count"] == 3
    assert result["updated_track_count"] == 2
    rows = list(csv.DictReader(output_csv.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["crop_label"] == "carried_panel"
    assert rows[1]["crop_label"] == "carried_panel"
    assert rows[2]["crop_label"] == "worker_only"
    assert "oracle:high:Visible wire mesh panel spans the sequence." in rows[0]["notes"]
    assert "oracle:medium:Worker silhouette without discrete panel edge." in rows[2]["notes"]


def test_apply_track_review_labels_refuses_unknown_crop_label(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [{"item_id": "diag-a-track-000005-crop-01", "crop_label": "unclear", "mask_status": "missing", "notes": ""}],
    )
    package_report = _write_json(
        tmp_path / "review_package.json",
        {
            "schema_version": "factory-crop-review-package-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [{"item_id": "diag-a-track-000005-crop-01", "diagnostic_id": "diag-a", "track_id": 5}],
        },
    )
    oracle_labels = _write_json(
        tmp_path / "oracle_labels.json",
        {"diag-a|5": {"crop_label": "panelish", "confidence": "low", "short_reason": "bad"}},
    )

    with pytest.raises(ValueError, match="Unsupported crop_label"):
        applier.apply_track_review_labels(
            review_package_report_path=package_report,
            oracle_labels_json_path=oracle_labels,
            output_csv_path=tmp_path / "out.csv",
            input_csv_path=None,
            force=False,
        )
