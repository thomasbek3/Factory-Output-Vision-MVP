from __future__ import annotations

import csv

import pytest

from scripts.convert_truth_review_worksheet_to_csv import main, read_accepted_events, write_truth_csv


FIELDNAMES = [
    "candidate_id",
    "human_decision_accept_countable",
    "exact_event_ts",
    "truth_event_id_if_accepted",
    "count_total_if_accepted",
    "reviewer",
    "review_notes",
]


def _write_worksheet(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_read_accepted_events_requires_all_rows_reviewed_and_exact_timestamps(tmp_path):
    worksheet = tmp_path / "worksheet.csv"
    _write_worksheet(
        worksheet,
        [
            {
                "candidate_id": "candidate-1",
                "human_decision_accept_countable": "yes",
                "exact_event_ts": "01:02.5",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "Thomas",
                "review_notes": "finished placement",
            },
            {
                "candidate_id": "candidate-2",
                "human_decision_accept_countable": "no",
                "exact_event_ts": "",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "Thomas",
                "review_notes": "worker motion only",
            },
        ],
    )

    events = read_accepted_events(worksheet, expected_total=1, truth_event_prefix="img2628-truth")

    assert events == [
        {
            "truth_event_id": "img2628-truth-0001",
            "count_total": 1,
            "event_ts": 62.5,
            "notes": "source_candidate=candidate-1; reviewer=Thomas; finished placement",
        }
    ]


def test_read_accepted_events_rejects_pending_rows(tmp_path):
    worksheet = tmp_path / "worksheet.csv"
    _write_worksheet(
        worksheet,
        [
            {
                "candidate_id": "candidate-1",
                "human_decision_accept_countable": "",
                "exact_event_ts": "",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "",
                "review_notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="pending row"):
        read_accepted_events(worksheet, expected_total=1, truth_event_prefix="img2628-truth")


def test_read_accepted_events_rejects_wrong_accepted_total(tmp_path):
    worksheet = tmp_path / "worksheet.csv"
    _write_worksheet(
        worksheet,
        [
            {
                "candidate_id": "candidate-1",
                "human_decision_accept_countable": "yes",
                "exact_event_ts": "5",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "",
                "review_notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="expected 2 accepted rows"):
        read_accepted_events(worksheet, expected_total=2, truth_event_prefix="img2628-truth")


def test_write_truth_csv_writes_ledger_builder_input(tmp_path):
    output = tmp_path / "truth.csv"
    events = [
        {"truth_event_id": "event-1", "count_total": 1, "event_ts": 5.0, "notes": "ok"},
    ]

    write_truth_csv(events, output, force=False)

    assert output.read_text(encoding="utf-8") == "truth_event_id,count_total,event_ts,notes\nevent-1,1,5.0,ok\n"


def test_main_reports_pending_rows_without_traceback(tmp_path, capsys):
    worksheet = tmp_path / "worksheet.csv"
    output = tmp_path / "truth.csv"
    _write_worksheet(
        worksheet,
        [
            {
                "candidate_id": "candidate-1",
                "human_decision_accept_countable": "",
                "exact_event_ts": "",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "",
                "review_notes": "",
            }
        ],
    )

    result = main(
        [
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
            "--expected-total",
            "1",
            "--truth-event-prefix",
            "img2628-truth",
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "error: worksheet still has 1 pending row" in captured.err
    assert "Traceback" not in captured.err
