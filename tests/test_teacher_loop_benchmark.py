from __future__ import annotations

import json
from pathlib import Path

from app.services.teacher_loop_benchmark import SCHEMA_VERSION, build_teacher_loop_benchmark
from scripts import run_teacher_loop_benchmark


def test_teacher_loop_benchmark_requires_real_teacher_when_all_dry_run_unclear(tmp_path: Path) -> None:
    proposals = _write_json(tmp_path / "event_proposals.json", {"summary": {"event_proposal_count": 10}})
    labels = _write_json(
        tmp_path / "teacher_labels.json",
        {
            "provider": {"network_calls_made": False},
            "labels": [
                {"packet_id": "a", "verification_decision": "unclear"},
                {"packet_id": "b", "verification_decision": "unclear"},
            ],
        },
    )
    fusion = _write_json(tmp_path / "fusion.json", {"summary": {"silver_candidate_count": 0, "needs_review_count": 2}})

    payload = build_teacher_loop_benchmark(
        event_proposals_path=proposals,
        teacher_labels_path=labels,
        fusion_report_path=fusion,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["benchmark_gate"]["status"] == "needs_real_teacher_or_more_evidence"
    assert payload["benchmark_gate"]["teacher_beats_no_teacher_baseline"] is False
    assert payload["no_teacher_baseline"]["training_eligible_count"] == 0
    assert payload["refuses_validation_truth"] is True


def test_teacher_loop_benchmark_passes_when_fusion_creates_silver_candidates(tmp_path: Path) -> None:
    proposals = _write_json(tmp_path / "event_proposals.json", {"summary": {"event_proposal_count": 10}})
    labels = _write_json(
        tmp_path / "teacher_labels.json",
        {"provider": {"network_calls_made": False}, "labels": [{"packet_id": "a", "verification_decision": "assert_completed"}]},
    )
    fusion = _write_json(
        tmp_path / "fusion.json",
        {"summary": {"silver_candidate_count": 2, "needs_review_count": 0, "hard_negative_count": 1}},
    )

    payload = build_teacher_loop_benchmark(
        event_proposals_path=proposals,
        teacher_labels_path=labels,
        fusion_report_path=fusion,
        min_silver_candidates=1,
    )

    assert payload["benchmark_gate"]["status"] == "teacher_pipeline_ready_for_replay_gate"
    assert payload["benchmark_gate"]["teacher_beats_no_teacher_baseline"] is True
    assert payload["teacher_pipeline"]["training_eligible_count"] == 2


def test_run_teacher_loop_benchmark_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = run_teacher_loop_benchmark.main(
        [
            "--event-proposals",
            str(tmp_path / "missing-proposals.json"),
            "--teacher-labels",
            str(tmp_path / "missing-labels.json"),
            "--fusion-report",
            str(tmp_path / "missing-fusion.json"),
            "--output",
            str(tmp_path / "out.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
