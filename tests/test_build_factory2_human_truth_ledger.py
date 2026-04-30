from __future__ import annotations

import json
from pathlib import Path

from scripts.build_factory2_human_truth_ledger import build_human_truth_ledger


def test_build_human_truth_ledger_merges_runtime_reconstruction_and_authority(tmp_path: Path) -> None:
    runtime_audit = tmp_path / "runtime_audit.json"
    runtime_audit.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_ts": 5.5,
                        "count_total": 1,
                        "track_id": 1,
                        "reason": "approved_delivery_chain",
                        "count_authority": "source_token_authorized",
                        "provenance_status": "inherited_live_source_token",
                    },
                    {
                        "event_ts": 42.701,
                        "count_total": 2,
                        "track_id": 11,
                        "reason": "approved_delivery_chain",
                        "count_authority": "runtime_inferred_only",
                        "provenance_status": "synthetic_approved_chain_token",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    reconstruction = tmp_path / "reconstruction.json"
    reconstruction.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "accepted-cluster-001",
                        "status": "proof_confirmed",
                        "counts_toward_reconstructed_total": True,
                        "runtime_event": {
                            "event_ts": 5.5,
                            "track_id": 1,
                        },
                        "proof_event": {
                            "track_key": "diag|1",
                            "diagnostic_id": "diag",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps(
            {
                "synthetic_without_distinct_proof_event_timestamps": [42.701],
                "proof_accepted_total": 21,
                "runtime_inferred_total": 23,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "ledger.json"

    payload = build_human_truth_ledger(
        runtime_audit_path=runtime_audit,
        reconstruction_path=reconstruction,
        authority_ledger_path=authority,
        output_path=output,
        expected_human_total=23,
        force=True,
    )

    assert payload["expected_human_total"] == 23
    assert payload["runtime_event_count"] == 2
    assert payload["matched_proof_confirmed_count"] == 1
    assert payload["needs_manual_confirmation_count"] == 1
    assert payload["events"][0]["truth_event_id"] == "factory2-truth-0001"
    assert payload["events"][0]["proof_status"] == "proof_confirmed"
    assert payload["events"][0]["proof_track_key"] == "diag|1"
    assert payload["events"][1]["authority_hint"] == "synthetic_without_distinct_proof"
    assert payload["events"][1]["needs_manual_confirmation"] is True
    assert output.exists()


def test_build_human_truth_ledger_requires_unique_runtime_matches(tmp_path: Path) -> None:
    runtime_audit = tmp_path / "runtime_audit.json"
    runtime_audit.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_ts": 10.0,
                        "count_total": 1,
                        "track_id": 1,
                        "reason": "approved_delivery_chain",
                        "count_authority": "source_token_authorized",
                        "provenance_status": "inherited_live_source_token",
                    },
                    {
                        "event_ts": 10.03,
                        "count_total": 2,
                        "track_id": 2,
                        "reason": "approved_delivery_chain",
                        "count_authority": "source_token_authorized",
                        "provenance_status": "inherited_live_source_token",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    reconstruction = tmp_path / "reconstruction.json"
    reconstruction.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "accepted-cluster-001",
                        "status": "proof_confirmed",
                        "counts_toward_reconstructed_total": True,
                        "runtime_event": {"event_ts": 10.02, "track_id": 999},
                        "proof_event": {"track_key": "diag|1", "diagnostic_id": "diag"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_human_truth_ledger(
        runtime_audit_path=runtime_audit,
        reconstruction_path=reconstruction,
        authority_ledger_path=None,
        output_path=tmp_path / "ledger.json",
        expected_human_total=23,
        force=True,
    )

    proof_statuses = [event["proof_status"] for event in payload["events"]]
    assert proof_statuses.count("proof_confirmed") == 1
    assert proof_statuses.count("runtime_only") == 1
