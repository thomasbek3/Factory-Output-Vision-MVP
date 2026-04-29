from __future__ import annotations

import json

from scripts.build_factory2_synthetic_lineage_report import build_synthetic_lineage_report


def test_build_synthetic_lineage_report_groups_events_by_provenance(tmp_path) -> None:
    runtime_path = tmp_path / "runtime.json"
    proof_path = tmp_path / "proof.json"
    divergence_path = tmp_path / "divergence.json"
    output_path = tmp_path / "report.json"
    runtime_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_ts": 100.0,
                        "track_id": 11,
                        "reason": "approved_delivery_chain",
                        "source_track_id": 7,
                        "source_token_id": "source-token-1",
                        "provenance_status": "synthetic_approved_chain_token",
                    },
                    {
                        "event_ts": 120.0,
                        "track_id": 12,
                        "reason": "approved_delivery_chain",
                        "source_track_id": 8,
                        "source_token_id": "source-token-2",
                        "provenance_status": "inherited_live_source_token",
                    },
                    {
                        "event_ts": 130.0,
                        "track_id": 99,
                        "reason": "stable_in_output",
                        "source_track_id": 9,
                        "source_token_id": "source-token-3",
                        "provenance_status": "source_zone_token",
                    },
                ],
                "track_histories": {
                    "7": [
                        {"timestamp": 90.0, "zone": "source"},
                        {"timestamp": 91.0, "zone": "source"},
                    ],
                    "8": [{"timestamp": 119.5, "zone": "source"}],
                    "11": [{"timestamp": 100.0, "zone": "output"}],
                },
            }
        ),
        encoding="utf-8",
    )
    proof_path.write_text(json.dumps({"accepted_count": 21}), encoding="utf-8")
    divergence_path.write_text(
        json.dumps(
            {
                "divergent_events": [
                    {
                        "event_ts": 100.0,
                        "proof_blocker": "synthetic_approved_chain_token",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_synthetic_lineage_report(
        runtime_audit_path=runtime_path,
        proof_report_path=proof_path,
        divergence_path=divergence_path,
        output_path=output_path,
        force=True,
    )

    assert payload["approved_delivery_chain_count"] == 2
    assert payload["synthetic_count"] == 1
    assert payload["inherited_live_count"] == 1
    assert payload["divergent_synthetic_count"] == 1
    assert payload["synthetic_with_overlapping_proof_count"] == 0
    assert payload["synthetic_without_overlapping_proof_count"] == 1
    assert payload["proof_accepted_count"] == 21
    assert payload["synthetic_events"][0]["source_gap_seconds"] == 9.0
    assert payload["synthetic_events"][0]["source_track_observation_count"] == 2
    assert payload["synthetic_events"][0]["output_track_observation_count"] == 1
    assert output_path.exists()


def test_build_synthetic_lineage_report_marks_divergent_runtime_events(tmp_path) -> None:
    runtime_path = tmp_path / "runtime.json"
    proof_path = tmp_path / "proof.json"
    divergence_path = tmp_path / "divergence.json"
    output_path = tmp_path / "report.json"
    runtime_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_ts": 305.708,
                        "track_id": 108,
                        "reason": "approved_delivery_chain",
                        "source_track_id": 105,
                        "source_token_id": "source-token-65",
                        "provenance_status": "synthetic_approved_chain_token",
                    }
                ],
                "track_histories": {
                    "105": [{"timestamp": 296.508, "zone": "source"}],
                    "108": [{"timestamp": 305.708, "zone": "output"}],
                },
            }
        ),
        encoding="utf-8",
    )
    proof_path.write_text(json.dumps({"accepted_count": 21}), encoding="utf-8")
    divergence_path.write_text(
        json.dumps(
            {
                "divergent_events": [
                    {
                        "event_ts": 305.708,
                        "proof_blocker": "synthetic_approved_chain_token",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_synthetic_lineage_report(
        runtime_audit_path=runtime_path,
        proof_report_path=proof_path,
        divergence_path=divergence_path,
        output_path=output_path,
        force=True,
    )

    assert payload["divergent_synthetic_count"] == 1
    assert payload["synthetic_without_overlapping_proof_event_timestamps"] == [305.708]
    assert payload["synthetic_events"][0]["is_divergent"] is True
    assert payload["synthetic_events"][0]["source_gap_seconds"] == 9.2
    assert payload["synthetic_events"][0]["has_overlapping_proof_receipt"] is False
    assert payload["synthetic_events"][0]["recommended_search_start_seconds"] == 295.508
    assert payload["synthetic_events"][0]["recommended_search_end_seconds"] == 307.708
