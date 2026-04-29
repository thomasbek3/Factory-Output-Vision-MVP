from __future__ import annotations

import json

from scripts.build_factory2_final_gap_search_plan import build_final_gap_search_plan


def test_build_final_gap_search_plan_generates_window_grid_for_unresolved_events(tmp_path) -> None:
    packets_path = tmp_path / "packets.json"
    output_path = tmp_path / "plan.json"
    packets_path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "recommendation": "shared_source_lineage_no_distinct_proof_receipt",
                        "covering_diagnostic_paths": [
                            "data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json"
                        ],
                        "prior_accepted_receipt": {
                            "track_id": 2,
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_final_gap_search_plan(
        packets_path=packets_path,
        output_path=output_path,
        lead_seconds=[4.0, 6.0],
        tail_seconds=[2.0],
        fps_values=[5.0, 8.0],
        force=True,
    )

    assert payload["event_count"] == 1
    assert payload["candidate_count"] == 4
    target = payload["targets"][0]
    assert target["event_id"] == "factory2-runtime-only-0007"
    assert target["baseline_source_token_key"] == "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002"
    assert target["covering_diagnostic_paths"] == [
        "data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json"
    ]
    assert target["candidates"][0]["start_seconds"] == 301.708
    assert target["candidates"][0]["end_seconds"] == 307.708
    assert target["candidates"][0]["fps"] == 5.0


def test_build_final_gap_search_plan_filters_non_shared_lineage_packets(tmp_path) -> None:
    packets_path = tmp_path / "packets.json"
    output_path = tmp_path / "plan.json"
    packets_path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "recommendation": "shared_source_lineage_no_distinct_proof_receipt",
                        "covering_diagnostic_paths": ["diag-a/diagnostic.json"],
                        "prior_accepted_receipt": {
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "source_token_key": "diag-a:tracks:000002",
                        },
                    },
                    {
                        "event_id": "factory2-runtime-only-0009",
                        "event_ts": 512.125,
                        "recommendation": "build_new_diagnostic",
                        "covering_diagnostic_paths": [],
                        "prior_accepted_receipt": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_final_gap_search_plan(
        packets_path=packets_path,
        output_path=output_path,
        lead_seconds=[4.0],
        tail_seconds=[2.0],
        fps_values=[5.0],
        force=True,
    )

    assert payload["event_count"] == 1
    assert payload["targets"][0]["event_id"] == "factory2-runtime-only-0007"
    assert output_path.exists()


def test_build_final_gap_search_plan_prefers_lineage_report_window_when_available(tmp_path) -> None:
    packets_path = tmp_path / "packets.json"
    lineage_report_path = tmp_path / "lineage.json"
    output_path = tmp_path / "plan.json"
    packets_path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "recommendation": "shared_source_lineage_no_distinct_proof_receipt",
                        "covering_diagnostic_paths": ["diag-a/diagnostic.json"],
                        "prior_accepted_receipt": {
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "source_token_key": "diag-a:tracks:000002",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    lineage_report_path.write_text(
        json.dumps(
            {
                "synthetic_events": [
                    {
                        "event_ts": 305.708,
                        "recommended_search_start_seconds": 289.708,
                        "recommended_search_end_seconds": 307.708,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_final_gap_search_plan(
        packets_path=packets_path,
        output_path=output_path,
        lead_seconds=[4.0],
        tail_seconds=[2.0],
        fps_values=[5.0, 8.0],
        lineage_report_path=lineage_report_path,
        force=True,
    )

    candidates = payload["targets"][0]["candidates"]
    assert candidates[0]["start_seconds"] == 289.708
    assert candidates[0]["end_seconds"] == 307.708
    assert candidates[0]["lineage_window"] is True
    assert len(candidates) == 2
