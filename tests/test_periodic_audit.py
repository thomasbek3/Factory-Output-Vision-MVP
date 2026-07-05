from __future__ import annotations

import json
from pathlib import Path

from app.services.periodic_audit import SCHEMA_VERSION, build_periodic_audit_report
from scripts.research.factory2 import run_periodic_audit


def _write_observed(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory2-app-observed-events-v1",
                "observed_event_count": 2,
                "events": [
                    {"event_ts": 1.0, "runtime_total_after_event": 1, "track_id": 10},
                    {"event_ts": 2.0, "runtime_total_after_event": 2, "track_id": 11},
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_teacher(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "case_id": "onboarding:line-a",
                "provider": {"network_calls_made": False},
                "refuses_validation_truth": True,
                "labels": [
                    {
                        "label_id": "event-10-audit",
                        "window_id": "event-10",
                        "teacher_output_status": "worker_only",
                        "label_authority_tier": "bronze",
                        "review_status": "pending",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                    {
                        "label_id": "event-11-audit",
                        "window_id": "event-11",
                        "teacher_output_status": "countable",
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


def test_periodic_audit_creates_disputes_and_retraining_triggers_without_total_mutation(tmp_path: Path) -> None:
    observed = tmp_path / "observed.json"
    teacher = tmp_path / "teacher.json"
    output = tmp_path / "audit.json"
    _write_observed(observed)
    _write_teacher(teacher)

    payload = build_periodic_audit_report(
        observed_events_path=observed,
        teacher_labels_path=teacher,
        output_path=output,
        force=True,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["runtime_total_before_audit"] == 2
    assert payload["runtime_total_after_audit"] == 2
    assert payload["runtime_total_mutation_allowed"] is False
    assert payload["count_authority"] == "existing_yolo_event_runtime_only"
    assert payload["teacher_labels_used_as_truth"] is False
    assert len(payload["disputes"]) == 1
    assert payload["disputes"][0]["mutates_runtime_total"] is False
    assert {row["trigger_type"] for row in payload["retraining_triggers"]} == {
        "hard_negative_candidate",
        "positive_candidate",
    }
    assert json.loads(observed.read_text())["observed_event_count"] == 2


def test_periodic_audit_cli_writes_report(tmp_path: Path, capsys) -> None:
    observed = tmp_path / "observed.json"
    teacher = tmp_path / "teacher.json"
    output = tmp_path / "audit.json"
    _write_observed(observed)
    _write_teacher(teacher)

    exit_code = run_periodic_audit.main(
        ["--observed-events", str(observed), "--teacher-labels", str(teacher), "--output", str(output), "--force"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"dispute_count": 1' in captured.out
    assert json.loads(output.read_text())["runtime_total_mutation_allowed"] is False
