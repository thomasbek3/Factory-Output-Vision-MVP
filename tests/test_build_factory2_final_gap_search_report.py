from __future__ import annotations

import json
from pathlib import Path

from scripts.build_factory2_final_gap_search_report import build_final_gap_search_report


def test_build_final_gap_search_report_marks_restated_lineage_as_nonrecovering(tmp_path) -> None:
    search_run_path = tmp_path / "run.json"
    output_path = tmp_path / "report.json"
    search_run_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "candidate_id": "cand-1",
                        "diagnostic_slug": "factory2-final-gap-search-0007-301-307s-8fps-v01",
                        "diagnostic_path": str(tmp_path / "diag-a" / "diagnostic.json"),
                        "baseline_source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_report_builder(*, diagnostic_paths, fp_report_paths, positive_report_paths):
        assert diagnostic_paths == [Path(tmp_path / "diag-a" / "diagnostic.json")]
        return {
            "decision_receipt_index": {
                "accepted": [
                    {
                        "diagnostic_path": str(tmp_path / "diag-a" / "diagnostic.json"),
                        "track_id": 2,
                        "source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                        "counts_toward_accepted_total": True,
                        "receipt_timestamps": {"first": 303.1, "last": 303.7},
                    }
                ],
                "suppressed": [],
                "uncertain": [],
            }
        }

    payload = build_final_gap_search_report(
        search_run_path=search_run_path,
        output_path=output_path,
        report_builder=fake_report_builder,
        fp_report_paths=[],
        positive_report_paths=[],
        force=True,
    )

    assert payload["result_count"] == 1
    assert payload["results"][0]["recommendation"] == "restated_prior_source_lineage"
    assert payload["results"][0]["accepted_track_id"] == 2


def test_build_final_gap_search_report_marks_fresh_lineage_candidate(tmp_path) -> None:
    search_run_path = tmp_path / "run.json"
    output_path = tmp_path / "report.json"
    search_run_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "event_id": "factory2-runtime-only-0008",
                        "event_ts": 425.012,
                        "candidate_id": "cand-2",
                        "diagnostic_slug": "factory2-final-gap-search-0008-417-427s-8fps-v01",
                        "diagnostic_path": str(tmp_path / "diag-b" / "diagnostic.json"),
                        "baseline_source_token_key": "factory2-review-0005-396-427s-panel-v2:tracks:000001-000003-000005",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_report_builder(*, diagnostic_paths, fp_report_paths, positive_report_paths):
        return {
            "decision_receipt_index": {
                "accepted": [
                    {
                        "diagnostic_path": str(tmp_path / "diag-b" / "diagnostic.json"),
                        "track_id": 9,
                        "source_token_key": "factory2-final-gap-search-0008-417-427s-8fps-v01:tracks:000004-000009",
                        "counts_toward_accepted_total": True,
                        "receipt_timestamps": {"first": 424.5, "last": 425.2},
                    }
                ],
                "suppressed": [],
                "uncertain": [],
            }
        }

    payload = build_final_gap_search_report(
        search_run_path=search_run_path,
        output_path=output_path,
        report_builder=fake_report_builder,
        fp_report_paths=[],
        positive_report_paths=[],
        force=True,
    )

    assert payload["results"][0]["recommendation"] == "fresh_source_lineage_candidate"
    assert payload["results"][0]["accepted_track_id"] == 9


def test_build_final_gap_search_report_marks_output_only_stub_when_no_accepted_receipt(tmp_path) -> None:
    search_run_path = tmp_path / "run.json"
    output_path = tmp_path / "report.json"
    search_run_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "candidate_id": "cand-3",
                        "diagnostic_slug": "factory2-final-gap-search-0007-301-307s-8fps-v02",
                        "diagnostic_path": str(tmp_path / "diag-c" / "diagnostic.json"),
                        "baseline_source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_report_builder(*, diagnostic_paths, fp_report_paths, positive_report_paths):
        return {
            "decision_receipt_index": {
                "accepted": [],
                "suppressed": [
                    {
                        "diagnostic_path": str(tmp_path / "diag-c" / "diagnostic.json"),
                        "track_id": 3,
                        "reason": "static_stack_edge",
                        "failure_link": "worker_body_overlap",
                        "receipt_timestamps": {"first": 306.8, "last": 306.8},
                    }
                ],
                "uncertain": [],
            }
        }

    payload = build_final_gap_search_report(
        search_run_path=search_run_path,
        output_path=output_path,
        report_builder=fake_report_builder,
        fp_report_paths=[],
        positive_report_paths=[],
        force=True,
    )

    assert payload["results"][0]["recommendation"] == "output_only_stub_only"
    assert payload["results"][0]["stub_track_id"] == 3


def test_build_final_gap_search_report_rejects_new_key_when_accepted_receipt_ends_before_event_and_stub_follows(tmp_path) -> None:
    search_run_path = tmp_path / "run.json"
    output_path = tmp_path / "report.json"
    search_run_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "candidate_id": "cand-4",
                        "diagnostic_slug": "factory2-final-gap-search-0007-301-307s-8fps-v03",
                        "diagnostic_path": str(tmp_path / "diag-d" / "diagnostic.json"),
                        "baseline_source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_report_builder(*, diagnostic_paths, fp_report_paths, positive_report_paths):
        return {
            "decision_receipt_index": {
                "accepted": [
                    {
                        "diagnostic_path": str(tmp_path / "diag-d" / "diagnostic.json"),
                        "track_id": 1,
                        "source_token_key": "factory2-final-gap-search-0007-301-307s-8fps-v03:tracks:000001",
                        "counts_toward_accepted_total": True,
                        "receipt_timestamps": {"first": 301.708, "last": 303.833},
                    }
                ],
                "suppressed": [
                    {
                        "diagnostic_path": str(tmp_path / "diag-d" / "diagnostic.json"),
                        "track_id": 2,
                        "reason": "static_stack_edge",
                        "failure_link": "worker_body_overlap",
                        "receipt_timestamps": {"first": 305.958, "last": 305.958},
                    }
                ],
                "uncertain": [],
            }
        }

    payload = build_final_gap_search_report(
        search_run_path=search_run_path,
        output_path=output_path,
        report_builder=fake_report_builder,
        fp_report_paths=[],
        positive_report_paths=[],
        force=True,
    )

    assert payload["results"][0]["recommendation"] == "shared_source_lineage_no_distinct_proof_receipt"
    assert payload["results"][0]["accepted_track_id"] == 1
    assert payload["results"][0]["stub_track_id"] == 2
