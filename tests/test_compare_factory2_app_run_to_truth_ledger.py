from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_factory2_app_run_to_truth_ledger import compare_app_run_to_truth_ledger


def test_compare_app_run_to_truth_ledger_finds_first_missing_truth_event(tmp_path: Path) -> None:
    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps(
            {
                "events": [
                    {"truth_event_id": "factory2-truth-0001", "event_ts": 5.5},
                    {"truth_event_id": "factory2-truth-0002", "event_ts": 23.6},
                    {"truth_event_id": "factory2-truth-0003", "event_ts": 42.7},
                ]
            }
        ),
        encoding="utf-8",
    )
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps(
            {
                "events": [
                    {"event_ts": 5.49, "track_id": 11, "runtime_total_after_event": 1},
                    {"event_ts": 42.68, "track_id": 22, "runtime_total_after_event": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = compare_app_run_to_truth_ledger(
        truth_ledger_path=truth,
        observed_events_path=observed,
        output_path=tmp_path / "comparison.json",
        tolerance_sec=0.2,
        force=True,
    )

    assert payload["matched_count"] == 2
    assert payload["missing_truth_count"] == 1
    assert payload["unexpected_observed_count"] == 0
    assert payload["first_divergence"]["type"] == "missing_truth"
    assert payload["first_divergence"]["truth_event_id"] == "factory2-truth-0002"


def test_compare_app_run_to_truth_ledger_reports_unexpected_observed_event(tmp_path: Path) -> None:
    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps(
            {
                "events": [
                    {"truth_event_id": "factory2-truth-0001", "event_ts": 5.5},
                ]
            }
        ),
        encoding="utf-8",
    )
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps(
            {
                "events": [
                    {"event_ts": 5.5, "track_id": 11, "runtime_total_after_event": 1},
                    {"event_ts": 9.9, "track_id": 22, "runtime_total_after_event": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = compare_app_run_to_truth_ledger(
        truth_ledger_path=truth,
        observed_events_path=observed,
        output_path=tmp_path / "comparison.json",
        tolerance_sec=0.1,
        force=True,
    )

    assert payload["matched_count"] == 1
    assert payload["missing_truth_count"] == 0
    assert payload["unexpected_observed_count"] == 1
    assert payload["first_divergence"]["type"] == "unexpected_observed"
    assert payload["first_divergence"]["track_id"] == 22


def test_compare_app_run_to_truth_ledger_marks_incomplete_coverage_before_calling_missing_truth(tmp_path: Path) -> None:
    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps(
            {
                "events": [
                    {"truth_event_id": "factory2-truth-0001", "event_ts": 5.5},
                    {"truth_event_id": "factory2-truth-0002", "event_ts": 23.6},
                    {"truth_event_id": "factory2-truth-0003", "event_ts": 42.7},
                    {"truth_event_id": "factory2-truth-0004", "event_ts": 60.5},
                    {"truth_event_id": "factory2-truth-0005", "event_ts": 78.6},
                ]
            }
        ),
        encoding="utf-8",
    )
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps(
            {
                "run_complete": False,
                "observed_coverage_end_sec": 60.502,
                "events": [
                    {"event_ts": 5.5, "track_id": 1, "runtime_total_after_event": 1},
                    {"event_ts": 23.6, "track_id": 2, "runtime_total_after_event": 2},
                    {"event_ts": 42.7, "track_id": 11, "runtime_total_after_event": 3},
                    {"event_ts": 60.5, "track_id": 16, "runtime_total_after_event": 4},
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = compare_app_run_to_truth_ledger(
        truth_ledger_path=truth,
        observed_events_path=observed,
        output_path=tmp_path / "comparison.json",
        tolerance_sec=0.2,
        force=True,
    )

    assert payload["matched_count"] == 4
    assert payload["missing_truth_count"] == 0
    assert payload["pending_truth_count"] == 1
    assert payload["first_divergence"]["type"] == "incomplete_coverage"
    assert payload["first_divergence"]["truth_event_id"] == "factory2-truth-0005"


def test_compare_app_run_to_truth_ledger_falls_back_to_last_observed_timestamp_for_incomplete_runs(tmp_path: Path) -> None:
    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps(
            {
                "events": [
                    {"truth_event_id": "factory2-truth-0001", "event_ts": 5.5},
                    {"truth_event_id": "factory2-truth-0002", "event_ts": 23.6},
                    {"truth_event_id": "factory2-truth-0003", "event_ts": 42.7},
                ]
            }
        ),
        encoding="utf-8",
    )
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps(
            {
                "run_complete": False,
                "events": [
                    {"event_ts": 5.5, "track_id": 1, "runtime_total_after_event": 1},
                    {"event_ts": 23.6, "track_id": 2, "runtime_total_after_event": 2},
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = compare_app_run_to_truth_ledger(
        truth_ledger_path=truth,
        observed_events_path=observed,
        output_path=tmp_path / "comparison.json",
        tolerance_sec=0.2,
        force=True,
    )

    assert payload["missing_truth_count"] == 0
    assert payload["pending_truth_count"] == 1
    assert payload["first_divergence"]["type"] == "incomplete_coverage"
