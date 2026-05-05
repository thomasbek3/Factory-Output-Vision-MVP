from __future__ import annotations

import pytest

from scripts.build_human_truth_ledger_from_csv import build_ledger, read_truth_events


def test_read_truth_events_accepts_seconds_and_minute_second_format(tmp_path):
    csv_path = tmp_path / "truth.csv"
    csv_path.write_text(
        "truth_event_id,count_total,event_ts,notes\n"
        "event-1,1,5.25,first\n"
        "event-2,2,01:12.5,second\n",
        encoding="utf-8",
    )

    events = read_truth_events(csv_path)

    assert events == [
        {"truth_event_id": "event-1", "count_total": 1, "event_ts": 5.25, "notes": "first"},
        {"truth_event_id": "event-2", "count_total": 2, "event_ts": 72.5, "notes": "second"},
    ]


def test_read_truth_events_rejects_missing_timestamps(tmp_path):
    csv_path = tmp_path / "truth.csv"
    csv_path.write_text(
        "truth_event_id,count_total,event_ts,notes\n"
        "event-1,1,,first\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="event_ts is required"):
        read_truth_events(csv_path)


def test_build_ledger_requires_expected_total_to_match(tmp_path):
    csv_path = tmp_path / "truth.csv"
    csv_path.write_text(
        "truth_event_id,count_total,event_ts,notes\n"
        "event-1,1,5,first\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected 2 events"):
        build_ledger(
            csv_path=csv_path,
            output_path=tmp_path / "ledger.json",
            video_path=tmp_path / "video.mov",
            expected_total=2,
            count_rule="count completions",
            video_sha256="abc",
            force=False,
        )
