from __future__ import annotations

from pathlib import Path

from scripts import optimize_factory2_proof_set as optimizer


def test_accepted_cluster_intervals_merge_duplicate_receipts() -> None:
    report = {
        "decision_receipt_index": {
            "accepted": [
                {
                    "accepted_cluster_id": "accepted-cluster-001",
                    "receipt_timestamps": {"first": 10.0, "last": 12.0},
                },
                {
                    "accepted_cluster_id": "accepted-cluster-001",
                    "receipt_timestamps": {"first": 11.5, "last": 13.0},
                },
                {
                    "accepted_cluster_id": "accepted-cluster-002",
                    "receipt_timestamps": {"first": 20.0, "last": 21.0},
                },
            ]
        }
    }

    assert optimizer.accepted_cluster_intervals(report) == [
        {"accepted_cluster_id": "accepted-cluster-001", "start_timestamp": 10.0, "end_timestamp": 13.0},
        {"accepted_cluster_id": "accepted-cluster-002", "start_timestamp": 20.0, "end_timestamp": 21.0},
    ]


def test_runtime_coverage_counts_events_with_tolerance() -> None:
    intervals = [
        {"accepted_cluster_id": "accepted-cluster-001", "start_timestamp": 10.0, "end_timestamp": 13.0},
        {"accepted_cluster_id": "accepted-cluster-002", "start_timestamp": 20.0, "end_timestamp": 21.0},
    ]

    coverage = optimizer.runtime_coverage(intervals=intervals, runtime_event_timestamps=[9.7, 12.5, 18.0, 21.4], tolerance_seconds=0.5)

    assert coverage.covered_count == 3
    assert coverage.covered_timestamps == [9.7, 12.5, 21.4]
    assert coverage.uncovered_timestamps == [18.0]


def test_optimize_proof_set_prefers_higher_coverage_then_lower_uncertainty(tmp_path: Path) -> None:
    base = [tmp_path / "base.json"]
    candidate_a = tmp_path / "candidate-a.json"
    candidate_b = tmp_path / "candidate-b.json"
    output = tmp_path / "optimized.json"

    reports_by_selection = {
        ("base.json",): {
            "accepted_count": 1,
            "accepted_receipt_count": 1,
            "accepted_duplicate_receipt_count": 0,
            "suppressed_count": 0,
            "uncertain_count": 0,
            "decision_receipt_index": {
                "accepted": [
                    {"accepted_cluster_id": "accepted-cluster-001", "receipt_timestamps": {"first": 10.0, "last": 10.2}},
                ]
            },
        },
        ("base.json", "candidate-a.json"): {
            "accepted_count": 2,
            "accepted_receipt_count": 2,
            "accepted_duplicate_receipt_count": 0,
            "suppressed_count": 1,
            "uncertain_count": 2,
            "decision_receipt_index": {
                "accepted": [
                    {"accepted_cluster_id": "accepted-cluster-001", "receipt_timestamps": {"first": 10.0, "last": 10.2}},
                    {"accepted_cluster_id": "accepted-cluster-002", "receipt_timestamps": {"first": 20.0, "last": 20.2}},
                ]
            },
        },
        ("base.json", "candidate-b.json"): {
            "accepted_count": 2,
            "accepted_receipt_count": 2,
            "accepted_duplicate_receipt_count": 0,
            "suppressed_count": 0,
            "uncertain_count": 6,
            "decision_receipt_index": {
                "accepted": [
                    {"accepted_cluster_id": "accepted-cluster-001", "receipt_timestamps": {"first": 10.0, "last": 10.2}},
                    {"accepted_cluster_id": "accepted-cluster-002", "receipt_timestamps": {"first": 20.0, "last": 20.2}},
                ]
            },
        },
        ("base.json", "candidate-a.json", "candidate-b.json"): {
            "accepted_count": 2,
            "accepted_receipt_count": 2,
            "accepted_duplicate_receipt_count": 0,
            "suppressed_count": 1,
            "uncertain_count": 9,
            "decision_receipt_index": {
                "accepted": [
                    {"accepted_cluster_id": "accepted-cluster-001", "receipt_timestamps": {"first": 10.0, "last": 10.2}},
                    {"accepted_cluster_id": "accepted-cluster-002", "receipt_timestamps": {"first": 20.0, "last": 20.2}},
                ]
            },
        },
    }

    def evaluate(paths: list[Path]) -> dict[str, object]:
        key = tuple(path.name for path in paths)
        return reports_by_selection[key]

    result = optimizer.optimize_proof_set(
        base_diagnostic_paths=base,
        candidate_diagnostic_paths=[candidate_a, candidate_b],
        runtime_event_timestamps=[10.1, 20.1],
        output_path=output,
        tolerance_seconds=0.25,
        force=True,
        evaluator=evaluate,
    )

    assert result["selected_candidate_paths"] == [str(candidate_a)]
    assert result["summary"]["covered_runtime_events"] == 2
    assert result["summary"]["accepted_count"] == 2
    assert result["summary"]["uncertain_count"] == 2
    assert output.exists()
