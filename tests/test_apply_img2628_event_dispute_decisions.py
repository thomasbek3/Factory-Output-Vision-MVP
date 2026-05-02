from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.apply_img2628_event_dispute_decisions import apply_decisions


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _base_truth(path: Path) -> None:
    _write_csv(
        path,
        [
            {"truth_event_id": "truth-001", "count_total": 1, "event_ts": 10.0, "notes": "base"},
            {"truth_event_id": "truth-002", "count_total": 2, "event_ts": 20.0, "notes": "base"},
        ],
        ["truth_event_id", "count_total", "event_ts", "notes"],
    )


def _disputes(path: Path) -> None:
    _write_csv(
        path,
        [
            {"issue_id": "issue-1"},
            {"issue_id": "issue-2"},
        ],
        ["issue_id"],
    )


def test_refuses_pending_decisions(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    decisions = tmp_path / "decisions.csv"
    disputes = tmp_path / "disputes.csv"
    _base_truth(base)
    _disputes(disputes)
    _write_csv(
        decisions,
        [
            {
                "issue_id": "issue-1",
                "decision": "",
                "reviewer": "",
                "review_notes": "",
                "app_event_ts": "12",
                "truth_event_ts": "",
                "replacement_event_ts": "",
                "truth_event_id": "",
            }
        ],
        [
            "issue_id",
            "decision",
            "reviewer",
            "review_notes",
            "app_event_ts",
            "truth_event_ts",
            "replacement_event_ts",
            "truth_event_id",
        ],
    )

    with pytest.raises(ValueError, match="decision must be one of"):
        apply_decisions(
            base_truth_path=base,
            decisions_path=decisions,
            disputes_path=disputes,
            output_path=tmp_path / "out.csv",
            expected_total=2,
            force=True,
        )


def test_refuses_missing_issue_decision(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    decisions = tmp_path / "decisions.csv"
    disputes = tmp_path / "disputes.csv"
    _base_truth(base)
    _disputes(disputes)
    _write_csv(
        decisions,
        [
            {
                "issue_id": "issue-1",
                "decision": "reject_app_event",
                "reviewer": "reviewer",
                "review_notes": "not countable",
                "app_event_ts": "12",
                "truth_event_ts": "",
                "replacement_event_ts": "",
                "truth_event_id": "",
            }
        ],
        [
            "issue_id",
            "decision",
            "reviewer",
            "review_notes",
            "app_event_ts",
            "truth_event_ts",
            "replacement_event_ts",
            "truth_event_id",
        ],
    )

    with pytest.raises(ValueError, match="missing decision rows for issue-2"):
        apply_decisions(
            base_truth_path=base,
            decisions_path=decisions,
            disputes_path=disputes,
            output_path=tmp_path / "out.csv",
            expected_total=2,
            force=True,
        )


def test_applies_reviewed_decisions(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    decisions = tmp_path / "decisions.csv"
    disputes = tmp_path / "disputes.csv"
    output = tmp_path / "out.csv"
    _base_truth(base)
    _disputes(disputes)
    _write_csv(
        decisions,
        [
            {
                "issue_id": "issue-1",
                "decision": "reject_app_event",
                "reviewer": "reviewer",
                "review_notes": "not countable",
                "app_event_ts": "12",
                "truth_event_ts": "",
                "replacement_event_ts": "",
                "truth_event_id": "",
            },
            {
                "issue_id": "issue-2",
                "decision": "match_app_to_truth",
                "reviewer": "reviewer",
                "review_notes": "same physical placement, finalize timestamp used",
                "app_event_ts": "22",
                "truth_event_ts": "20",
                "replacement_event_ts": "22",
                "truth_event_id": "truth-002",
            },
        ],
        [
            "issue_id",
            "decision",
            "reviewer",
            "review_notes",
            "app_event_ts",
            "truth_event_ts",
            "replacement_event_ts",
            "truth_event_id",
        ],
    )

    result = apply_decisions(
        base_truth_path=base,
        decisions_path=decisions,
        disputes_path=disputes,
        output_path=output,
        expected_total=2,
        force=True,
    )

    assert result["event_count"] == 2
    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert [row["event_ts"] for row in rows] == ["10.000", "22.000"]
    assert [row["count_total"] for row in rows] == ["1", "2"]


def test_can_align_reviewed_events_to_observed_app_timestamps(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    decisions = tmp_path / "decisions.csv"
    disputes = tmp_path / "disputes.csv"
    observed = tmp_path / "observed.json"
    output = tmp_path / "out.csv"
    _base_truth(base)
    _disputes(disputes)
    _write_csv(
        decisions,
        [
            {
                "issue_id": "issue-1",
                "decision": "reject_app_event",
                "reviewer": "reviewer",
                "review_notes": "not countable",
                "app_event_ts": "12",
                "truth_event_ts": "",
                "replacement_event_ts": "",
                "truth_event_id": "",
            },
            {
                "issue_id": "issue-2",
                "decision": "keep_truth_event",
                "reviewer": "reviewer",
                "review_notes": "still countable",
                "app_event_ts": "",
                "truth_event_ts": "20",
                "replacement_event_ts": "",
                "truth_event_id": "truth-002",
            },
        ],
        [
            "issue_id",
            "decision",
            "reviewer",
            "review_notes",
            "app_event_ts",
            "truth_event_ts",
            "replacement_event_ts",
            "truth_event_id",
        ],
    )
    observed.write_text(
        json.dumps(
            {
                "events": [
                    {"event_ts": 10.25, "runtime_total_after_event": 1, "track_id": 101},
                    {"event_ts": 21.5, "runtime_total_after_event": 2, "track_id": 102},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = apply_decisions(
        base_truth_path=base,
        decisions_path=decisions,
        disputes_path=disputes,
        output_path=output,
        expected_total=2,
        observed_events_path=observed,
        max_align_delta_sec=2.0,
        force=True,
    )

    assert result["aligned_to_observed_events"] is True
    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert [row["event_ts"] for row in rows] == ["10.250", "21.500"]
    assert "aligned_visible_app_event_ts=10.250" in rows[0]["notes"]
