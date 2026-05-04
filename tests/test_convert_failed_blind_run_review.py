from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.check_dataset_poisoning import run_checks
from scripts.convert_failed_blind_run_review import ReviewConversionError, convert_review


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    fieldnames = [
        "row_type",
        "candidate_id",
        "source_id",
        "center_timestamp",
        "start_timestamp",
        "end_timestamp",
        "runtime_track_id",
        "runtime_travel_px",
        "suggested_review_decision",
        "review_decision",
        "reviewed_event_ts",
        "sheet_path",
        "clip_path",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _packet() -> dict[str, object]:
    return {
        "schema_version": "factory-vision-failed-blind-run-learning-packet-v1",
        "case_id": "real_factory_candidate",
        "privacy_mode": "offline_local",
        "expected_true_total": 2,
        "truth_review_slots": [
            {"slot_id": "real_factory_candidate-truth-slot-0001", "candidate_type": "true_placement_slot"},
            {"slot_id": "real_factory_candidate-truth-slot-0002", "candidate_type": "true_placement_slot"},
        ],
        "false_positive_candidates": [
            {
                "candidate_id": "real_factory_candidate-hard-negative-0001",
                "candidate_type": "runtime_false_positive_candidate",
                "event_ts": 12.0,
                "sheet_path": "data/events/sheet-1.jpg",
                "clip_path": "data/events/clip-1.mp4",
            },
            {
                "candidate_id": "real_factory_candidate-hard-negative-0002",
                "candidate_type": "runtime_false_positive_candidate",
                "event_ts": 55.0,
                "sheet_path": "data/events/sheet-2.jpg",
                "clip_path": "data/events/clip-2.mp4",
            },
        ],
        "motion_window_candidates": [
            {
                "candidate_id": "real_factory_candidate-motion-window-0001",
                "candidate_type": "possible_true_or_missed_event_window",
                "center_timestamp": 42.0,
                "sheet_path": "data/events/sheet-3.jpg",
                "clip_path": "data/events/clip-3.mp4",
            }
        ],
    }


def _manifest() -> dict[str, object]:
    return {
        "case_id": "real_factory_candidate",
        "video": {
            "path": "data/videos/from-pc/real_factory.MOV",
            "sha256": "48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86",
        },
        "truth": {
            "count_rule": "Count one completed placement when the worker finishes putting the finished product in the output/resting area.",
            "expected_total": 2,
        },
    }


def _outputs(tmp_path: Path) -> dict[str, Path]:
    return {
        "status_path": tmp_path / "conversion_status.json",
        "truth_csv_path": tmp_path / "truth.csv",
        "truth_ledger_path": tmp_path / "truth_ledger.json",
        "review_labels_path": tmp_path / "review_labels.json",
        "dataset_manifest_path": tmp_path / "dataset_manifest.json",
    }


def test_pending_worksheet_writes_bronze_status_without_truth_outputs(tmp_path: Path) -> None:
    packet_path = _write_json(tmp_path / "packet.json", _packet())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())
    worksheet_path = _write_csv(
        tmp_path / "worksheet.csv",
        [
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0001",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0001",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0002",
            },
            {
                "row_type": "possible_true_or_missed_event_window",
                "candidate_id": "real_factory_candidate-motion-window-0001",
            },
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0002",
            },
        ],
    )
    outputs = _outputs(tmp_path)

    with pytest.raises(ReviewConversionError, match="pending"):
        convert_review(
            worksheet_path=worksheet_path,
            packet_path=packet_path,
            manifest_path=manifest_path,
            allow_pending=False,
            force=True,
            **outputs,
        )

    status = convert_review(
        worksheet_path=worksheet_path,
        packet_path=packet_path,
        manifest_path=manifest_path,
        allow_pending=True,
        force=True,
        **outputs,
    )

    assert status["status"] == "pending_human_review"
    assert status["accepted_true_placement_count"] == 0
    assert status["pending_row_count"] == 5
    assert status["validation_truth_eligible"] is False
    assert status["training_eligible"] is False
    assert outputs["status_path"].exists()
    assert outputs["review_labels_path"].exists()
    assert outputs["dataset_manifest_path"].exists()
    assert not outputs["truth_csv_path"].exists()
    assert not outputs["truth_ledger_path"].exists()

    review_labels = json.loads(outputs["review_labels_path"].read_text(encoding="utf-8"))
    assert {label["label_authority_tier"] for label in review_labels["labels"]} == {"bronze"}
    assert {label["review_status"] for label in review_labels["labels"]} == {"pending"}
    run_checks(datasets=[outputs["dataset_manifest_path"]], teacher_labels=[], truth_artifacts=[])


def test_reviewed_worksheet_writes_gold_truth_and_training_anchors(tmp_path: Path) -> None:
    packet_path = _write_json(tmp_path / "packet.json", _packet())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())
    worksheet_path = _write_csv(
        tmp_path / "worksheet.csv",
        [
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0001",
                "review_decision": "true_placement",
                "reviewed_event_ts": "42.5",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0001",
                "review_decision": "hard_negative_static",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0002",
                "review_decision": "duplicate",
            },
            {
                "row_type": "possible_true_or_missed_event_window",
                "candidate_id": "real_factory_candidate-motion-window-0001",
                "review_decision": "background",
            },
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0002",
                "review_decision": "true_placement",
                "reviewed_event_ts": "1:05.250",
            },
        ],
    )
    outputs = _outputs(tmp_path)

    status = convert_review(
        worksheet_path=worksheet_path,
        packet_path=packet_path,
        manifest_path=manifest_path,
        allow_pending=False,
        force=True,
        reviewer_id="thomas",
        **outputs,
    )

    assert status["status"] == "reviewed_complete"
    assert status["accepted_true_placement_count"] == 2
    assert status["hard_negative_label_count"] == 3
    assert status["validation_truth_eligible"] is True
    assert status["training_eligible"] is True

    truth_rows = list(csv.DictReader(outputs["truth_csv_path"].open(newline="", encoding="utf-8")))
    assert [(row["count_total"], row["event_ts"]) for row in truth_rows] == [("1", "42.5"), ("2", "65.25")]

    ledger = json.loads(outputs["truth_ledger_path"].read_text(encoding="utf-8"))
    assert ledger["schema_version"] == "human-truth-ledger-v1"
    assert ledger["video_path"] == "data/videos/from-pc/real_factory.MOV"
    assert ledger["video_sha256"] == "48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86"
    assert [event["count_total"] for event in ledger["events"]] == [1, 2]

    review_labels = json.loads(outputs["review_labels_path"].read_text(encoding="utf-8"))
    assert review_labels["reviewer"]["id"] == "thomas"
    assert sum(1 for label in review_labels["labels"] if label["approved_status"] == "completed") == 2
    assert all(label["label_authority_tier"] == "gold" for label in review_labels["labels"])

    dataset = json.loads(outputs["dataset_manifest_path"].read_text(encoding="utf-8"))
    assert dataset["schema_version"] == "factory-vision-active-learning-dataset-v1"
    assert dataset["summary"]["true_placement_count"] == 2
    assert dataset["summary"]["hard_negative_count"] == 3
    assert dataset["detector_training"]["positive_box_labels_ready"] is False
    assert "positive bounding boxes" in dataset["detector_training"]["blocked_reason"]
    run_checks(
        datasets=[outputs["dataset_manifest_path"]],
        teacher_labels=[],
        truth_artifacts=[outputs["truth_ledger_path"]],
    )


def test_reviewed_worksheet_requires_exact_true_total(tmp_path: Path) -> None:
    packet_path = _write_json(tmp_path / "packet.json", _packet())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())
    worksheet_path = _write_csv(
        tmp_path / "worksheet.csv",
        [
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0001",
                "review_decision": "true_placement",
                "reviewed_event_ts": "42.5",
            },
            {
                "row_type": "true_placement_slot",
                "candidate_id": "real_factory_candidate-truth-slot-0002",
                "review_decision": "background",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0001",
                "review_decision": "hard_negative_static",
            },
            {
                "row_type": "runtime_false_positive_candidate",
                "candidate_id": "real_factory_candidate-hard-negative-0002",
                "review_decision": "hard_negative_static",
            },
            {
                "row_type": "possible_true_or_missed_event_window",
                "candidate_id": "real_factory_candidate-motion-window-0001",
                "review_decision": "background",
            },
        ],
    )
    outputs = _outputs(tmp_path)

    with pytest.raises(ReviewConversionError, match="expected 2 true placement"):
        convert_review(
            worksheet_path=worksheet_path,
            packet_path=packet_path,
            manifest_path=manifest_path,
            allow_pending=False,
            force=True,
            **outputs,
        )
