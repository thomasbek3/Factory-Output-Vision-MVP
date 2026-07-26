from __future__ import annotations

import json
from pathlib import Path

from app.services.teacher_fusion import SCHEMA_VERSION, build_teacher_fusion_report
from scripts import fuse_teacher_verifications


def test_teacher_fusion_promotes_only_asserted_state_change_to_silver(tmp_path: Path) -> None:
    labels = _write_labels(tmp_path)
    state = _write_state_diff(tmp_path)
    silver_dataset = tmp_path / "silver_dataset.json"

    payload = build_teacher_fusion_report(
        teacher_labels_path=labels,
        state_diff_path=state,
        output_dataset_path=silver_dataset,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["refuses_validation_truth"] is True
    assert payload["summary"]["silver_candidate_count"] == 1
    decisions = {row["packet_id"]: row for row in payload["decisions"]}
    assert decisions["packet-change"]["fusion_decision"] == "promote_to_silver_training_candidate"
    assert decisions["packet-change"]["training_candidate"] is True
    assert decisions["packet-change"]["training_eligible"] is False
    assert decisions["packet-stable"]["fusion_decision"] == "hard_negative_candidate"
    assert decisions["packet-stable"]["training_eligible"] is False
    dataset = json.loads(silver_dataset.read_text(encoding="utf-8"))
    assert dataset["validation_truth_eligible"] is False
    assert dataset["requires_blind_replay_gate"] is True
    assert dataset["training_candidate"] is True
    assert dataset["training_eligible"] is False


def test_fuse_teacher_verifications_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = fuse_teacher_verifications.main(
        [
            "--teacher-labels",
            str(tmp_path / "missing-labels.json"),
            "--state-diff",
            str(tmp_path / "missing-state.json"),
            "--output",
            str(tmp_path / "out.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err


def _write_labels(tmp_path: Path) -> Path:
    path = tmp_path / "teacher_labels.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "labels": [
                    {
                        "label_id": "change-label",
                        "packet_id": "packet-change",
                        "window_id": "packet-change-window",
                        "candidate_id": "packet-change-candidate",
                        "verification_decision": "assert_completed",
                        "teacher_output_status": "completed",
                        "duplicate_risk": "unknown",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                    {
                        "label_id": "stable-label",
                        "packet_id": "packet-stable",
                        "window_id": "packet-stable-window",
                        "candidate_id": "packet-stable-candidate",
                        "verification_decision": "refute_completed",
                        "teacher_output_status": "worker_only",
                        "duplicate_risk": "unknown",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_state_diff(tmp_path: Path) -> Path:
    path = tmp_path / "state_diff.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-state-diff-reconciliation-v1",
                "rows": [
                    {
                        "packet_id": "packet-change",
                        "state_change_detected": True,
                        "reconciliation_status": "matched_asserted_change",
                    },
                    {
                        "packet_id": "packet-stable",
                        "state_change_detected": False,
                        "reconciliation_status": "matched_refuted_no_change",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
