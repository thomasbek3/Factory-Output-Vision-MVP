from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.capture_factory2_app_run_events import write_observed_events_report


def test_write_observed_events_report_sorts_and_trims_recent_count_events(tmp_path: Path) -> None:
    diagnostics = {
        "current_state": "RUNNING_GREEN",
        "demo_playback_finished": False,
        "reader_last_sequence_index": 606,
        "reader_last_source_timestamp_sec": 60.502,
        "recent_count_events": [
            {"event_ts": 23.6, "track_id": 2, "runtime_total_after_event": 2},
            {"event_ts": 5.5, "track_id": 1, "runtime_total_after_event": 1},
        ],
    }
    output = tmp_path / "observed.json"

    payload = write_observed_events_report(
        diagnostics_payload=diagnostics,
        output_path=output,
        metadata={"mode": "test"},
        force=True,
    )

    assert payload["observed_event_count"] == 2
    assert payload["run_complete"] is False
    assert payload["observed_coverage_end_sec"] == 60.502
    assert payload["events"][0]["track_id"] == 1
    assert payload["events"][1]["track_id"] == 2
    assert payload["metadata"]["mode"] == "test"
    assert json.loads(output.read_text(encoding="utf-8"))["events"][0]["event_ts"] == 5.5


def test_write_observed_events_report_rejects_existing_file_without_force(tmp_path: Path) -> None:
    output = tmp_path / "observed.json"
    output.write_text("{}", encoding="utf-8")

    try:
        write_observed_events_report(
            diagnostics_payload={"recent_count_events": []},
            output_path=output,
            metadata={},
            force=False,
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")
