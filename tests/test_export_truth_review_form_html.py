from __future__ import annotations

import csv
import json

from scripts.export_truth_review_form_html import build_html, main


FIELDNAMES = [
    "candidate_id",
    "draft_center_ts_sec",
    "window_start_sec",
    "window_end_sec",
    "motion_score",
    "contact_strip_path",
    "human_decision_accept_countable",
    "exact_event_ts",
    "truth_event_id_if_accepted",
    "count_total_if_accepted",
    "reviewer",
    "review_notes",
]


def _write_worksheet(path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "candidate-1",
                "draft_center_ts_sec": "10.000",
                "window_start_sec": "2.000",
                "window_end_sec": "18.000",
                "motion_score": "12.5",
                "contact_strip_path": "data/videos/review_frames/example.jpg",
                "human_decision_accept_countable": "",
                "exact_event_ts": "",
                "truth_event_id_if_accepted": "",
                "count_total_if_accepted": "",
                "reviewer": "",
                "review_notes": "",
            }
        )


def test_build_html_marks_page_as_human_review_aid(tmp_path):
    worksheet = tmp_path / "worksheet.csv"
    windows = tmp_path / "windows.json"
    output = tmp_path / "form.html"
    _write_worksheet(worksheet)
    windows.write_text(json.dumps({"case_id": "img2628_candidate"}), encoding="utf-8")

    html = build_html(
        worksheet_path=worksheet,
        candidate_windows_path=windows,
        output_path=output,
        expected_total=25,
    )

    assert "IMG_2628 Interactive Truth Review" in html
    assert "Human review aid only" in html
    assert "Expected accepted placements: 25" in html
    assert "candidate-1" in html
    assert "Export worksheet CSV" in html
    assert "validation truth" in html


def test_main_writes_form(tmp_path):
    worksheet = tmp_path / "worksheet.csv"
    windows = tmp_path / "windows.json"
    output = tmp_path / "form.html"
    _write_worksheet(worksheet)
    windows.write_text(json.dumps({"case_id": "img2628_candidate"}), encoding="utf-8")

    result = main(
        [
            "--worksheet",
            str(worksheet),
            "--candidate-windows",
            str(windows),
            "--output",
            str(output),
            "--expected-total",
            "25",
        ]
    )

    assert result == 0
    assert output.exists()
    assert "candidate-1" in output.read_text(encoding="utf-8")
