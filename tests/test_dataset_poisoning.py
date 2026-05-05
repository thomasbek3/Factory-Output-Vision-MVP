from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_dataset_poisoning import DatasetPoisoningError, run_checks


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_check_dataset_poisoning_rejects_teacher_labels_as_validation_truth(tmp_path: Path) -> None:
    teacher_path = _write_json(
        tmp_path / "teacher_labels.json",
        {
            "schema_version": "factory-vision-teacher-labels-v1",
            "case_id": "fixture",
            "source_evidence_path": "evidence.json",
            "privacy_mode": "offline_local",
            "provider": {"name": "dry_run_fixture", "mode": "local_fixture", "network_calls_made": False},
            "refuses_validation_truth": True,
            "labels": [],
        },
    )

    with pytest.raises(DatasetPoisoningError, match="teacher/VLM artifacts cannot be validation truth"):
        run_checks(datasets=[], teacher_labels=[], truth_artifacts=[teacher_path])


def test_check_dataset_poisoning_rejects_unreviewed_teacher_gold(tmp_path: Path) -> None:
    teacher_path = _write_json(
        tmp_path / "teacher_labels.json",
        {
            "schema_version": "factory-vision-teacher-labels-v1",
            "case_id": "fixture",
            "source_evidence_path": "evidence.json",
            "privacy_mode": "offline_local",
            "provider": {"name": "dry_run_fixture", "mode": "local_fixture", "network_calls_made": False},
            "refuses_validation_truth": True,
            "labels": [
                {
                    "label_id": "bad",
                    "window_id": "w1",
                    "teacher_output_status": "completed",
                    "confidence_tier": "high",
                    "duplicate_risk": "low",
                    "miss_risk": "low",
                    "label_authority_tier": "gold",
                    "review_status": "pending",
                    "validation_truth_eligible": False,
                    "training_eligible": False,
                }
            ],
        },
    )

    with pytest.raises(DatasetPoisoningError, match="unreviewed teacher label is in gold set"):
        run_checks(datasets=[], teacher_labels=[teacher_path], truth_artifacts=[])


def test_check_dataset_poisoning_rejects_train_test_window_overlap(tmp_path: Path) -> None:
    dataset_path = _write_json(
        tmp_path / "dataset.json",
        {
            "schema_version": "factory-vision-active-learning-dataset-v1",
            "dataset_id": "fixture",
            "case_ids": ["fixture_case"],
            "privacy_mode": "offline_local",
            "label_tier_policy": {
                "validation_truth_requires_gold": True,
                "bronze_training_allowed": False,
                "silver_validation_allowed": False,
            },
            "splits": {
                "train": [{"window_id": "same"}],
                "test": [{"window_id": "same"}],
            },
            "items": [
                {
                    "item_id": "same-train",
                    "case_id": "fixture_case",
                    "window_id": "same",
                    "split": "train",
                    "label_authority_tier": "gold",
                    "review_status": "approved",
                    "teacher_output_status": "completed",
                    "duplicate_risk": "low",
                    "miss_risk": "low",
                    "validation_truth_eligible": True,
                    "training_eligible": True,
                }
            ],
        },
    )

    with pytest.raises(DatasetPoisoningError, match="train/test split overlap"):
        run_checks(datasets=[dataset_path], teacher_labels=[], truth_artifacts=[])


def test_check_dataset_poisoning_accepts_bronze_review_queue_item(tmp_path: Path) -> None:
    dataset_path = _write_json(
        tmp_path / "dataset.json",
        {
            "schema_version": "factory-vision-active-learning-dataset-v1",
            "dataset_id": "fixture",
            "case_ids": ["fixture_case"],
            "privacy_mode": "offline_local",
            "label_tier_policy": {
                "validation_truth_requires_gold": True,
                "bronze_training_allowed": False,
                "silver_validation_allowed": False,
            },
            "splits": {"review": [{"window_id": "w1"}]},
            "items": [
                {
                    "item_id": "w1-review",
                    "case_id": "fixture_case",
                    "window_id": "w1",
                    "split": "review",
                    "label_authority_tier": "bronze",
                    "review_status": "pending",
                    "teacher_output_status": "unclear",
                    "duplicate_risk": "unknown",
                    "miss_risk": "unknown",
                    "validation_truth_eligible": False,
                    "training_eligible": False,
                }
            ],
        },
    )

    assert run_checks(datasets=[dataset_path], teacher_labels=[], truth_artifacts=[])["ok"] is True
