from __future__ import annotations

import json
from pathlib import Path

from scripts.build_review_queue import build_review_queue


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    evidence_path = tmp_path / "evidence.json"
    teacher_path = tmp_path / "teacher.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-event-evidence-v1",
                "case_id": "fixture_case",
                "privacy_mode": "offline_local",
                "video": {"path": "video.mov", "sha256": "abc"},
                "source_artifacts": {"observed_events_path": "observed.json"},
                "model_settings": {},
                "windows": [
                    {
                        "window_id": "easy-count",
                        "window_type": "count_event",
                        "time_window": {"start_sec": 1.0, "center_sec": 2.0, "end_sec": 3.0},
                        "frame_window": {"center_frame_index": 20},
                        "review_window": {
                            "review_question": "Is this a completed placement?",
                            "frame_assets": [
                                {
                                    "timestamp_sec": 2.0,
                                    "frame_path": "frames/easy.jpg",
                                    "sha256": "easy",
                                    "status": "written",
                                }
                            ],
                        },
                        "confidence_tier": "unknown",
                        "duplicate_risk": "unknown",
                        "miss_risk": "unknown",
                        "label_authority_tier": "bronze",
                    },
                    {
                        "window_id": "needs-review",
                        "window_type": "count_event",
                        "time_window": {"start_sec": 4.0, "center_sec": 5.0, "end_sec": 6.0},
                        "frame_window": {"center_frame_index": 50},
                        "review_window": {
                            "review_question": "Is this a completed placement?",
                            "frame_assets": [
                                {
                                    "timestamp_sec": 5.0,
                                    "frame_path": "frames/review.jpg",
                                    "sha256": "review",
                                    "status": "written",
                                }
                            ],
                        },
                        "confidence_tier": "unknown",
                        "duplicate_risk": "unknown",
                        "miss_risk": "unknown",
                        "label_authority_tier": "bronze",
                    },
                    {
                        "window_id": "hard-negative",
                        "window_type": "count_event",
                        "time_window": {"start_sec": 7.0, "center_sec": 8.0, "end_sec": 9.0},
                        "frame_window": {"center_frame_index": 80},
                        "review_window": {
                            "review_question": "Is this a completed placement?",
                            "frame_assets": [
                                {
                                    "timestamp_sec": 8.0,
                                    "frame_path": "frames/worker.jpg",
                                    "sha256": "worker",
                                    "status": "written",
                                }
                            ],
                        },
                        "confidence_tier": "unknown",
                        "duplicate_risk": "unknown",
                        "miss_risk": "unknown",
                        "label_authority_tier": "bronze",
                    },
                ],
                "review_window_metadata": [],
            }
        ),
        encoding="utf-8",
    )
    teacher_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "case_id": "fixture_case",
                "source_evidence_path": evidence_path.as_posix(),
                "privacy_mode": "offline_local",
                "provider": {
                    "name": "moondream_station",
                    "mode": "local_http",
                    "model": "moondream-2",
                    "network_calls_made": True,
                },
                "refuses_validation_truth": True,
                "labels": [
                    {
                        "label_id": "easy-count-label",
                        "window_id": "easy-count",
                        "teacher_output_status": "countable",
                        "suggested_event_ts_sec": 2.0,
                        "confidence_tier": "high",
                        "duplicate_risk": "low",
                        "miss_risk": "low",
                        "rationale": "Visible completed placement.",
                        "label_authority_tier": "bronze",
                        "review_status": "pending",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                    {
                        "label_id": "needs-review-label",
                        "window_id": "needs-review",
                        "teacher_output_status": "unclear",
                        "suggested_event_ts_sec": 5.0,
                        "confidence_tier": "low",
                        "duplicate_risk": "high",
                        "miss_risk": "unknown",
                        "rationale": "Cannot be determined from the image.",
                        "label_authority_tier": "bronze",
                        "review_status": "pending",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                    {
                        "label_id": "hard-negative-label",
                        "window_id": "hard-negative",
                        "teacher_output_status": "worker_only",
                        "suggested_event_ts_sec": 8.0,
                        "confidence_tier": "high",
                        "duplicate_risk": "low",
                        "miss_risk": "low",
                        "rationale": "Worker only.",
                        "label_authority_tier": "bronze",
                        "review_status": "pending",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return evidence_path, teacher_path


def test_review_queue_ranks_unclear_and_risky_windows_first(tmp_path: Path) -> None:
    evidence_path, teacher_path = _write_fixture_files(tmp_path)

    payload = build_review_queue(evidence_path=evidence_path, teacher_labels_path=teacher_path)

    assert payload["schema_version"] == "factory-vision-review-queue-v1"
    assert payload["refuses_validation_truth"] is True
    assert [entry["window_id"] for entry in payload["queue"]] == [
        "needs-review",
        "hard-negative",
        "easy-count",
    ]
    first = payload["queue"][0]
    assert first["priority_bucket"] == "review_first"
    assert "teacher_unclear" in first["review_reasons"]
    assert "duplicate_risk_high" in first["review_reasons"]


def test_review_queue_carries_frame_assets_and_safety_flags(tmp_path: Path) -> None:
    evidence_path, teacher_path = _write_fixture_files(tmp_path)

    payload = build_review_queue(evidence_path=evidence_path, teacher_labels_path=teacher_path)
    hard_negative = next(entry for entry in payload["queue"] if entry["window_id"] == "hard-negative")

    assert hard_negative["primary_frame_asset"]["frame_path"] == "frames/worker.jpg"
    assert hard_negative["frame_assets"][0]["sha256"] == "worker"
    assert hard_negative["candidate_use"] == "hard_negative_review"
    assert hard_negative["validation_truth_eligible"] is False
    assert hard_negative["training_eligible"] is False
    assert hard_negative["review_status"] == "pending"
