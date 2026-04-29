from __future__ import annotations

import json

from scripts.reconstruct_factory2_truth_candidates import (
    build_truth_reconstruction,
    collapse_manual_track_candidates,
    load_proof_confirmed_events,
)


def test_load_proof_confirmed_events_filters_noncanonical_duplicates(tmp_path) -> None:
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "accepted_cluster_id": "accepted-cluster-001",
                            "counts_toward_accepted_total": True,
                            "diagnostic_path": "/tmp/diag-a/diagnostic.json",
                            "track_id": 3,
                            "receipt_timestamps": {"first": 11.6, "last": 23.6},
                            "receipt_json_path": "diag-a/track-000003.json",
                            "receipt_card_path": "diag-a/track-000003-sheet.jpg",
                        },
                        {
                            "accepted_cluster_id": "accepted-cluster-001",
                            "counts_toward_accepted_total": False,
                            "diagnostic_path": "/tmp/diag-b/diagnostic.json",
                            "track_id": 1,
                            "receipt_timestamps": {"first": 22.0, "last": 24.0},
                            "receipt_json_path": "diag-b/track-000001.json",
                            "receipt_card_path": "diag-b/track-000001-sheet.jpg",
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    events = load_proof_confirmed_events(proof_path)

    assert len(events) == 1
    assert events[0].accepted_cluster_id == "accepted-cluster-001"
    assert events[0].track_key == "diag-a|3"


def test_collapse_manual_track_candidates_groups_overlapping_tracks() -> None:
    candidates = collapse_manual_track_candidates(
        [
            {"track_key": "diag-a|1", "diagnostic_id": "diag-a", "track_id": 1, "start_timestamp": 0.0, "end_timestamp": 5.0},
            {"track_key": "diag-a|2", "diagnostic_id": "diag-a", "track_id": 2, "start_timestamp": 4.8, "end_timestamp": 4.8},
            {"track_key": "diag-b|1", "diagnostic_id": "diag-b", "track_id": 1, "start_timestamp": 10.0, "end_timestamp": 12.0},
        ]
    )

    assert len(candidates) == 2
    assert candidates[0]["track_count"] == 2
    assert candidates[1]["track_count"] == 1


def test_build_truth_reconstruction_emits_proof_runtime_and_manual_sections(tmp_path) -> None:
    proof_path = tmp_path / "proof.json"
    runtime_path = tmp_path / "runtime.json"
    labels_path = tmp_path / "labels.json"
    diagnostics_root = tmp_path / "diagnostics"
    output_path = tmp_path / "reconstruction.json"

    proof_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "accepted_cluster_id": "accepted-cluster-001",
                            "counts_toward_accepted_total": True,
                            "diagnostic_path": str(tmp_path / "diag-a" / "diagnostic.json"),
                            "track_id": 3,
                            "receipt_timestamps": {"first": 11.6, "last": 23.6},
                            "receipt_json_path": "diag-a/track-000003.json",
                            "receipt_card_path": "diag-a/track-000003-sheet.jpg",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    runtime_path.write_text(
        json.dumps(
            {
                "events": [
                    {"event_ts": 23.6, "track_id": 101, "count_total": 1, "reason": "approved_delivery_chain"},
                    {"event_ts": 60.5, "track_id": 102, "count_total": 2, "reason": "approved_delivery_chain"},
                ]
            }
        ),
        encoding="utf-8",
    )

    (diagnostics_root / "diag-a" / "track_receipts").mkdir(parents=True)
    (diagnostics_root / "diag-a" / "track_receipts" / "track-000003.json").write_text(
        json.dumps({"timestamps": {"first": 11.6, "last": 23.6}}),
        encoding="utf-8",
    )
    (diagnostics_root / "diag-b" / "track_receipts").mkdir(parents=True)
    (diagnostics_root / "diag-b" / "track_receipts" / "track-000001.json").write_text(
        json.dumps({"timestamps": {"first": 70.0, "last": 75.0}}),
        encoding="utf-8",
    )
    labels_path.write_text(
        json.dumps(
            {
                "diag-a|3": {
                    "confidence": "high",
                    "crop_label": "carried_panel",
                    "short_reason": "proof-backed",
                },
                "diag-b|1": {
                    "confidence": "high",
                    "crop_label": "carried_panel",
                    "short_reason": "manual-only",
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_truth_reconstruction(
        proof_report_path=proof_path,
        runtime_audit_path=runtime_path,
        manual_labels_path=labels_path,
        diagnostics_root=diagnostics_root,
        output_path=output_path,
        runtime_match_slack_seconds=0.5,
        force=True,
    )

    assert report["proof_confirmed_count"] == 1
    assert report["runtime_only_count"] == 1
    assert report["manual_only_candidate_count"] == 1
    assert report["events"][0]["status"] == "proof_confirmed"
    assert report["events"][0]["runtime_event"]["track_id"] == 101
    assert report["events"][1]["status"] == "runtime_only_needs_receipt_match"
    assert report["events"][2]["status"] == "manual_crop_visible_needs_source_output_chain"
    assert output_path.exists()
