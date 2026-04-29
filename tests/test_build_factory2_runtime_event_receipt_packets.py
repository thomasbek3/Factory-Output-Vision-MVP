from __future__ import annotations

import json
from pathlib import Path

from scripts.build_factory2_runtime_event_receipt_packets import build_runtime_event_receipt_packets


def test_build_runtime_event_receipt_packets_marks_prior_receipt_plus_stub_as_shared_source_risk(tmp_path: Path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    proof_report_path = tmp_path / "proof.json"
    output_path = tmp_path / "packets.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {
                            "event_ts": 305.708,
                            "track_id": 108,
                            "count_total": 22,
                            "reason": "approved_delivery_chain",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proof_report_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 288.0, "end_timestamp": 328.0},
                            "track_id": 2,
                            "decision": "allow_source_token",
                            "reason": "moving_panel_candidate",
                            "failure_link": "source_token_approved",
                            "source_token_key": "diag:track-000001",
                            "source_lineage_track_ids": [1],
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "receipt_json_path": "diag/track_receipts/track-000002.json",
                            "receipt_card_path": "diag/track_receipts/track-000002-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-2.jpg"],
                            "counts_toward_accepted_total": True,
                        }
                    ],
                    "suppressed": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 288.0, "end_timestamp": 328.0},
                            "track_id": 3,
                            "decision": "reject",
                            "reason": "static_stack_edge",
                            "failure_link": "static_stack_or_resident_output",
                            "source_token_key": None,
                            "source_lineage_track_ids": [],
                            "receipt_timestamps": {"first": 306.9, "last": 306.9},
                            "receipt_json_path": "diag/track_receipts/track-000003.json",
                            "receipt_card_path": "diag/track_receipts/track-000003-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-3.jpg"],
                        }
                    ],
                    "uncertain": [],
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_runtime_event_receipt_packets(
        reconstruction_path=reconstruction_path,
        proof_report_path=proof_report_path,
        output_path=output_path,
        packet_slack_seconds=2.0,
        force=True,
    )

    assert payload["packet_count"] == 1
    packet = payload["packets"][0]
    assert packet["recommendation"] == "shared_source_lineage_no_distinct_proof_receipt"
    assert packet["prior_accepted_receipt"]["track_id"] == 2
    assert packet["nearest_output_only_stub_receipt"]["track_id"] == 3
    assert packet["shared_source_lineage_risk"] is True
    assert "output-only stub" in packet["reason_strings"][0]
    assert output_path.exists()


def test_build_runtime_event_receipt_packets_requests_new_diagnostic_when_no_covering_receipt_exists(tmp_path: Path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    proof_report_path = tmp_path / "proof.json"
    output_path = tmp_path / "packets.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0009",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {
                            "event_ts": 512.125,
                            "track_id": 209,
                            "count_total": 24,
                            "reason": "approved_delivery_chain",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proof_report_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [],
                    "suppressed": [],
                    "uncertain": [],
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_runtime_event_receipt_packets(
        reconstruction_path=reconstruction_path,
        proof_report_path=proof_report_path,
        output_path=output_path,
        packet_slack_seconds=2.0,
        force=True,
    )

    packet = payload["packets"][0]
    assert packet["recommendation"] == "build_new_diagnostic"
    assert packet["covering_receipt_count"] == 0
    assert packet["prior_accepted_receipt"] is None
    assert packet["nearest_output_only_stub_receipt"] is None


def test_build_runtime_event_receipt_packets_backfills_source_lineage_from_receipt_json(tmp_path: Path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    proof_report_path = tmp_path / "proof.json"
    output_path = tmp_path / "packets.json"
    receipt_path = tmp_path / "diag" / "track_receipts" / "track-000002.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "perception_gate": {
                    "track_id": 2,
                    "decision": "allow_source_token",
                    "reason": "moving_panel_candidate",
                    "flags": ["source_token_allowed_by_crop_classifier"],
                    "evidence": {
                        "track_id": 2,
                        "source_frames": 0,
                        "output_frames": 1,
                        "merged_predecessor_track_ids": [1],
                        "merged_predecessor_receipt_paths": [str(tmp_path / "diag" / "track_receipts" / "track-000001.json")],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {
                            "event_ts": 305.708,
                            "track_id": 108,
                            "count_total": 22,
                            "reason": "approved_delivery_chain",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proof_report_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 288.0, "end_timestamp": 328.0},
                            "track_id": 2,
                            "decision": "allow_source_token",
                            "reason": "moving_panel_candidate",
                            "failure_link": "source_token_approved",
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "receipt_json_path": str(receipt_path),
                            "receipt_card_path": "diag/track_receipts/track-000002-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-2.jpg"],
                            "counts_toward_accepted_total": True,
                        }
                    ],
                    "suppressed": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 288.0, "end_timestamp": 328.0},
                            "track_id": 3,
                            "decision": "reject",
                            "reason": "static_stack_edge",
                            "failure_link": "static_stack_or_resident_output",
                            "receipt_timestamps": {"first": 306.9, "last": 306.9},
                            "receipt_json_path": "diag/track_receipts/track-000003.json",
                            "receipt_card_path": "diag/track_receipts/track-000003-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-3.jpg"],
                        }
                    ],
                    "uncertain": [],
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_runtime_event_receipt_packets(
        reconstruction_path=reconstruction_path,
        proof_report_path=proof_report_path,
        output_path=output_path,
        packet_slack_seconds=2.0,
        force=True,
    )

    packet = payload["packets"][0]
    assert packet["shared_source_lineage_risk"] is True
    assert packet["prior_accepted_receipt"]["source_token_key"] == "diag:tracks:000001"


def test_build_runtime_event_receipt_packets_treats_static_stack_reason_as_stub_even_if_failure_link_is_worker_overlap(tmp_path: Path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    proof_report_path = tmp_path / "proof.json"
    output_path = tmp_path / "packets.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0008",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {
                            "event_ts": 425.012,
                            "track_id": 152,
                            "count_total": 23,
                            "reason": "approved_delivery_chain",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proof_report_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 396.0, "end_timestamp": 427.0},
                            "track_id": 5,
                            "decision": "allow_source_token",
                            "reason": "moving_panel_candidate",
                            "failure_link": "source_token_approved",
                            "source_token_key": "diag:tracks:000001-000003-000005",
                            "source_lineage_track_ids": [1, 3, 5],
                            "receipt_timestamps": {"first": 422.167, "last": 422.5},
                            "receipt_json_path": "diag/track_receipts/track-000005.json",
                            "receipt_card_path": "diag/track_receipts/track-000005-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-5.jpg"],
                            "counts_toward_accepted_total": True,
                        }
                    ],
                    "suppressed": [
                        {
                            "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                            "window": {"start_timestamp": 396.0, "end_timestamp": 427.0},
                            "track_id": 6,
                            "decision": "reject",
                            "reason": "static_stack_edge",
                            "failure_link": "worker_body_overlap",
                            "receipt_timestamps": {"first": 424.833, "last": 424.833},
                            "receipt_json_path": "diag/track_receipts/track-000006.json",
                            "receipt_card_path": "diag/track_receipts/track-000006-sheet.jpg",
                            "raw_crop_paths": ["diag/crop-6.jpg"],
                        }
                    ],
                    "uncertain": [],
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_runtime_event_receipt_packets(
        reconstruction_path=reconstruction_path,
        proof_report_path=proof_report_path,
        output_path=output_path,
        packet_slack_seconds=2.0,
        force=True,
    )

    packet = payload["packets"][0]
    assert packet["recommendation"] == "shared_source_lineage_no_distinct_proof_receipt"
    assert packet["nearest_output_only_stub_receipt"]["track_id"] == 6
