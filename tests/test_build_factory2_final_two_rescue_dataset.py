from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import build_factory2_final_two_rescue_dataset as builder


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
                "relation_label",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_build_final_two_rescue_dataset_uses_relation_labels_and_groups_tracks(tmp_path: Path) -> None:
    same_a = _write_image(tmp_path / "package" / "images" / "same-a.jpg", b"same-a")
    same_b = _write_image(tmp_path / "package" / "images" / "same-b.jpg", b"same-b")
    distinct = _write_image(tmp_path / "package" / "images" / "distinct.jpg", b"distinct")
    unclear = _write_image(tmp_path / "package" / "images" / "unclear.jpg", b"unclear")
    review_csv = _write_review_csv(
        tmp_path / "package" / "review_labels.csv",
        [
            {
                "item_id": "event-7-track-000107-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "prior delivery",
            },
            {
                "item_id": "event-7-track-000107-obs-02",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "",
            },
            {
                "item_id": "event-8-track-000145-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "distinct_new_delivery",
                "notes": "earlier separate chain",
            },
            {
                "item_id": "event-8-track-000152-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "unclear",
                "notes": "",
            },
        ],
    )
    review_report = _write_json(
        tmp_path / "package" / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "event-7-track-000107-obs-01",
                    "event_id": "factory2-runtime-only-0007",
                    "track_id": 107,
                    "track_role": "prior_runtime_event",
                    "track_class": "source_to_output",
                    "crop_image_path": str(same_a),
                    "frame_image_path": str(same_a),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                },
                {
                    "item_id": "event-7-track-000107-obs-02",
                    "event_id": "factory2-runtime-only-0007",
                    "track_id": 107,
                    "track_role": "prior_runtime_event",
                    "track_class": "source_to_output",
                    "crop_image_path": str(same_b),
                    "frame_image_path": str(same_b),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                },
                {
                    "item_id": "event-8-track-000145-obs-01",
                    "event_id": "factory2-runtime-only-0008",
                    "track_id": 145,
                    "track_role": "source_anchor",
                    "track_class": "source_only",
                    "crop_image_path": str(distinct),
                    "frame_image_path": str(distinct),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                },
                {
                    "item_id": "event-8-track-000152-obs-01",
                    "event_id": "factory2-runtime-only-0008",
                    "track_id": 152,
                    "track_role": "divergent_runtime_event",
                    "track_class": "output_only",
                    "crop_image_path": str(unclear),
                    "frame_image_path": str(unclear),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                },
            ],
        },
    )

    output_report = tmp_path / "out" / "rescue_dataset.json"
    out_dir = tmp_path / "out" / "dataset"

    result = builder.build_final_two_rescue_dataset(
        review_report_path=review_report,
        output_report_path=output_report,
        dataset_dir=out_dir,
        review_labels_csv_path=None,
        force=False,
    )

    assert result["schema_version"] == "factory2-final-two-rescue-dataset-v1"
    assert result["target_mode"] == "relation_classifier"
    assert result["eligible_item_count"] == 3
    assert result["skipped_unclear_relation_count"] == 1
    assert result["relation_label_counts"] == {
        "distinct_new_delivery": 1,
        "same_delivery_as_prior": 2,
    }
    assert result["missing_relation_classes"] == ["static_resident"]
    assert result["ready_for_training"] is False
    assert len(result["items"]) == 3
    assert result["items"][0]["relation_label"] == "distinct_new_delivery"
    assert result["items"][1]["relation_label"] == "same_delivery_as_prior"
    assert result["items"][2]["relation_label"] == "same_delivery_as_prior"
    assert result["items"][1]["split"] == result["items"][2]["split"]
    assert Path(result["items"][0]["image_path"]).read_bytes() == b"distinct"
    assert Path(result["items"][1]["image_path"]).read_bytes() == b"same-a"
    assert Path(result["items"][2]["image_path"]).read_bytes() == b"same-b"
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_build_final_two_rescue_dataset_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    image = _write_image(tmp_path / "package" / "images" / "panel.jpg", b"panel")
    review_csv = _write_review_csv(
        tmp_path / "package" / "review_labels.csv",
        [
            {
                "item_id": "event-7-track-000107-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "",
            }
        ],
    )
    review_report = _write_json(
        tmp_path / "package" / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "event-7-track-000107-obs-01",
                    "event_id": "factory2-runtime-only-0007",
                    "track_id": 107,
                    "track_role": "prior_runtime_event",
                    "track_class": "source_to_output",
                    "crop_image_path": str(image),
                    "frame_image_path": str(image),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                }
            ],
        },
    )
    output_report = tmp_path / "out" / "rescue_dataset.json"
    out_dir = tmp_path / "out" / "dataset"

    builder.build_final_two_rescue_dataset(
        review_report_path=review_report,
        output_report_path=output_report,
        dataset_dir=out_dir,
        review_labels_csv_path=None,
        force=False,
    )

    with pytest.raises(FileExistsError):
        builder.build_final_two_rescue_dataset(
            review_report_path=review_report,
            output_report_path=output_report,
            dataset_dir=out_dir,
            review_labels_csv_path=None,
            force=False,
        )


def test_build_final_two_rescue_dataset_can_include_static_reference_items(tmp_path: Path) -> None:
    same = _write_image(tmp_path / "package" / "images" / "same.jpg", b"same")
    static_ref = _write_image(tmp_path / "static" / "static.jpg", b"static")
    review_csv = _write_review_csv(
        tmp_path / "package" / "review_labels.csv",
        [
            {
                "item_id": "event-7-track-000107-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "",
            }
        ],
    )
    review_report = _write_json(
        tmp_path / "package" / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "items": [
                {
                    "item_id": "event-7-track-000107-obs-01",
                    "event_id": "factory2-runtime-only-0007",
                    "track_id": 107,
                    "track_role": "prior_runtime_event",
                    "track_class": "source_to_output",
                    "crop_image_path": str(same),
                    "frame_image_path": str(same),
                    "label_placeholder": {
                        "crop_label": "unclear",
                        "relation_label": "unclear",
                        "notes": "",
                    },
                }
            ],
        },
    )
    static_reference_report = _write_json(
        tmp_path / "static_refs.json",
        {
            "schema_version": "factory2-static-resident-reference-crops-v1",
            "items": [
                {
                    "item_id": "static-ref-000001",
                    "diagnostic_id": "diag-static",
                    "track_id": 3,
                    "event_id": "static-resident-reference",
                    "track_role": "static_resident_reference",
                    "track_class": "output_only",
                    "exported_crop_path": str(static_ref),
                    "label_placeholder": {
                        "crop_label": "carried_panel",
                        "relation_label": "static_resident",
                        "notes": "proof static stack edge reference",
                    },
                }
            ],
        },
    )

    result = builder.build_final_two_rescue_dataset(
        review_report_path=review_report,
        output_report_path=tmp_path / "out" / "rescue_dataset.json",
        dataset_dir=tmp_path / "out" / "dataset",
        review_labels_csv_path=None,
        static_reference_report_path=static_reference_report,
        force=False,
    )

    assert result["eligible_item_count"] == 2
    assert result["relation_label_counts"] == {
        "same_delivery_as_prior": 1,
        "static_resident": 1,
    }
    assert result["missing_relation_classes"] == ["distinct_new_delivery"]
    assert Path(result["items"][0]["image_path"]).read_bytes() in {b"same", b"static"}
