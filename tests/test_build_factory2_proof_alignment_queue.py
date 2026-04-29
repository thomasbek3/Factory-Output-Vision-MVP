from __future__ import annotations

import json

from scripts.build_factory2_proof_alignment_queue import build_proof_alignment_queue


def test_build_proof_alignment_queue_maps_runtime_only_events_to_covering_diagnostics(tmp_path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    output_path = tmp_path / "queue.json"
    diag_a = tmp_path / "diag-a.json"
    diag_b = tmp_path / "diag-b.json"
    diag_c = tmp_path / "diag-c.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0001",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 42.701, "track_id": 11, "count_total": 3},
                    },
                    {
                        "event_id": "factory2-runtime-only-0002",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 60.502, "track_id": 16, "count_total": 4},
                    },
                    {
                        "event_id": "factory2-runtime-only-0003",
                        "status": "proof_confirmed",
                        "runtime_event": {"event_ts": 147.004, "track_id": 44, "count_total": 8},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    diag_a.write_text(
        json.dumps({"window": {"start_timestamp": 0.0, "end_timestamp": 78.0}}),
        encoding="utf-8",
    )
    diag_b.write_text(
        json.dumps({"window": {"start_timestamp": 58.0, "end_timestamp": 99.0}}),
        encoding="utf-8",
    )
    diag_c.write_text(
        json.dumps({"window": {"start_timestamp": 112.0, "end_timestamp": 152.0}}),
        encoding="utf-8",
    )

    report = build_proof_alignment_queue(
        reconstruction_path=reconstruction_path,
        output_path=output_path,
        active_proof_diagnostic_paths=[diag_a],
        candidate_diagnostic_paths=[diag_a, diag_b, diag_c],
        padding_seconds=20.0,
        force=True,
    )

    assert report["runtime_only_count"] == 2
    assert report["queue_count"] == 2

    first = report["queue"][0]
    assert first["event_id"] == "factory2-runtime-only-0001"
    assert first["covered_by_active_proof"] is True
    assert first["preferred_diagnostic_path"] == str(diag_a)
    assert first["suggested_action"] == "inspect_existing_diagnostic"
    assert first["suggested_start_seconds"] == 22.701
    assert first["suggested_end_seconds"] == 62.701

    second = report["queue"][1]
    assert second["event_id"] == "factory2-runtime-only-0002"
    assert second["covered_by_active_proof"] is True
    assert second["preferred_diagnostic_path"] == str(diag_b)
    assert second["covering_existing_diagnostic_paths"] == [str(diag_a), str(diag_b)]
    assert second["suggested_action"] == "inspect_existing_diagnostic"

    assert output_path.exists()


def test_build_proof_alignment_queue_reads_top_level_diagnostic_timestamps(tmp_path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    output_path = tmp_path / "queue.json"
    diag_a = tmp_path / "diag-a.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0003",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 60.502, "track_id": 16, "count_total": 4},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    diag_a.write_text(
        json.dumps({"start_timestamp": 58.0, "end_timestamp": 99.0}),
        encoding="utf-8",
    )

    report = build_proof_alignment_queue(
        reconstruction_path=reconstruction_path,
        output_path=output_path,
        active_proof_diagnostic_paths=[],
        candidate_diagnostic_paths=[diag_a],
        padding_seconds=20.0,
        force=True,
    )

    row = report["queue"][0]
    assert row["preferred_diagnostic_path"] == str(diag_a)
    assert row["suggested_action"] == "inspect_existing_diagnostic"


def test_build_proof_alignment_queue_marks_uncovered_events_for_new_diagnostic(tmp_path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    output_path = tmp_path / "queue.json"
    diag_a = tmp_path / "diag-a.json"

    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0008",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 425.012, "track_id": 152, "count_total": 23},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    diag_a.write_text(
        json.dumps({"window": {"start_timestamp": 0.0, "end_timestamp": 78.0}}),
        encoding="utf-8",
    )

    report = build_proof_alignment_queue(
        reconstruction_path=reconstruction_path,
        output_path=output_path,
        active_proof_diagnostic_paths=[diag_a],
        candidate_diagnostic_paths=[diag_a],
        padding_seconds=20.0,
        force=True,
    )

    row = report["queue"][0]
    assert row["covered_by_active_proof"] is False
    assert row["preferred_diagnostic_path"] is None
    assert row["suggested_action"] == "build_new_diagnostic"
    assert row["suggested_start_seconds"] == 405.012
    assert row["suggested_end_seconds"] == 445.012
