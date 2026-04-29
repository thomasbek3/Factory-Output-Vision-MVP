from __future__ import annotations

import json

from scripts.analyze_factory2_runtime_truth_gap import (
    ReviewedTrack,
    build_truth_gap_report,
    collapse_truth_intervals,
    match_runtime_events,
)


def test_collapse_truth_intervals_groups_only_overlapping_tracks() -> None:
    intervals = collapse_truth_intervals(
        [
            ReviewedTrack(
                diagnostic_id="diag-a",
                track_id=1,
                start_timestamp=0.0,
                end_timestamp=5.0,
                crop_label="carried_panel",
                confidence="high",
                short_reason="first",
            ),
            ReviewedTrack(
                diagnostic_id="diag-a",
                track_id=2,
                start_timestamp=4.8,
                end_timestamp=4.8,
                crop_label="carried_panel",
                confidence="medium",
                short_reason="overlap",
            ),
            ReviewedTrack(
                diagnostic_id="diag-b",
                track_id=3,
                start_timestamp=5.1,
                end_timestamp=6.0,
                crop_label="carried_panel",
                confidence="medium",
                short_reason="new physical carry",
            ),
        ],
        gap_seconds=0.0,
    )

    assert len(intervals) == 2
    assert intervals[0].start_timestamp == 0.0
    assert intervals[0].end_timestamp == 5.0
    assert [item.track_id for item in intervals[0].tracks] == [1, 2]
    assert [item.track_id for item in intervals[1].tracks] == [3]


def test_match_runtime_events_reports_missing_and_extra_events() -> None:
    intervals = collapse_truth_intervals(
        [
            ReviewedTrack(
                diagnostic_id="diag-a",
                track_id=1,
                start_timestamp=0.0,
                end_timestamp=5.0,
                crop_label="carried_panel",
                confidence="high",
                short_reason="first",
            ),
            ReviewedTrack(
                diagnostic_id="diag-b",
                track_id=2,
                start_timestamp=10.0,
                end_timestamp=12.0,
                crop_label="carried_panel",
                confidence="high",
                short_reason="second",
            ),
            ReviewedTrack(
                diagnostic_id="diag-c",
                track_id=3,
                start_timestamp=20.0,
                end_timestamp=22.0,
                crop_label="carried_panel",
                confidence="high",
                short_reason="third",
            ),
        ],
        gap_seconds=0.0,
    )
    runtime_events = [
        {"event_ts": 5.4, "track_id": 11, "count_total": 1, "reason": "approved_delivery_chain"},
        {"event_ts": 11.6, "track_id": 12, "count_total": 2, "reason": "approved_delivery_chain"},
        {"event_ts": 30.0, "track_id": 13, "count_total": 3, "reason": "approved_delivery_chain"},
    ]

    diff = match_runtime_events(intervals, runtime_events, slack_seconds=0.5)

    assert diff["matched_truth_count"] == 2
    assert diff["missing_truth_count"] == 1
    assert diff["extra_runtime_event_count"] == 1
    assert diff["matched_truth_intervals"][0]["matched_event"]["track_id"] == 11
    assert diff["missing_truth_intervals"][0]["truth_interval_id"] == "factory2-truth-0003"
    assert diff["extra_runtime_events"][0]["track_id"] == 13


def test_build_truth_gap_report_reads_manual_track_receipts(tmp_path) -> None:
    diagnostics_root = tmp_path / "data" / "diagnostics" / "event-windows"
    labels_path = tmp_path / "data" / "reports" / "factory2_track_labels.manual_v1.json"
    runtime_audit_path = tmp_path / "data" / "reports" / "runtime_audit.json"
    output_path = tmp_path / "data" / "reports" / "runtime_truth_gap.json"

    track_receipts = diagnostics_root / "diag-a" / "track_receipts"
    track_receipts.mkdir(parents=True)
    (track_receipts / "track-000001.json").write_text(
        json.dumps({"timestamps": {"first": 0.0, "last": 5.0}}),
        encoding="utf-8",
    )
    (track_receipts / "track-000002.json").write_text(
        json.dumps({"timestamps": {"first": 4.8, "last": 4.8}}),
        encoding="utf-8",
    )
    track_receipts = diagnostics_root / "diag-b" / "track_receipts"
    track_receipts.mkdir(parents=True)
    (track_receipts / "track-000003.json").write_text(
        json.dumps({"timestamps": {"first": 10.0, "last": 12.0}}),
        encoding="utf-8",
    )

    labels_path.parent.mkdir(parents=True)
    labels_path.write_text(
        json.dumps(
            {
                "diag-a|1": {
                    "confidence": "high",
                    "crop_label": "carried_panel",
                    "short_reason": "first",
                },
                "diag-a|2": {
                    "confidence": "medium",
                    "crop_label": "carried_panel",
                    "short_reason": "overlap",
                },
                "diag-b|3": {
                    "confidence": "high",
                    "crop_label": "carried_panel",
                    "short_reason": "second",
                },
            }
        ),
        encoding="utf-8",
    )
    runtime_audit_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_audit_path.write_text(
        json.dumps(
            {
                "events": [
                    {"event_ts": 5.4, "track_id": 11, "count_total": 1, "reason": "approved_delivery_chain"},
                    {"event_ts": 30.0, "track_id": 12, "count_total": 2, "reason": "approved_delivery_chain"},
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_truth_gap_report(
        labels_path=labels_path,
        runtime_audit_path=runtime_audit_path,
        output_path=output_path,
        diagnostics_root=diagnostics_root,
        gap_seconds=0.0,
        slack_seconds=0.5,
        force=True,
    )

    assert report["truth_interval_count"] == 2
    assert report["matched_truth_count"] == 1
    assert report["missing_truth_count"] == 1
    assert report["extra_runtime_event_count"] == 1
    assert output_path.exists()
