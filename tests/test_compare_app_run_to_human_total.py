from __future__ import annotations

import json

from scripts.compare_app_run_to_human_total import compare_app_run_to_human_total


def test_compare_app_run_to_human_total_reports_match(tmp_path):
    human_total_path = tmp_path / "human.json"
    observed_path = tmp_path / "observed.json"
    output_path = tmp_path / "comparison.json"
    human_total_path.write_text(json.dumps({"expected_human_total": 2}), encoding="utf-8")
    observed_path.write_text(
        json.dumps({"observed_event_count": 2, "run_complete": True, "observed_coverage_end_sec": 10.0}),
        encoding="utf-8",
    )

    payload = compare_app_run_to_human_total(
        human_total_path=human_total_path,
        observed_events_path=observed_path,
        output_path=output_path,
        force=False,
    )

    assert payload["total_matches"] is True
    assert payload["delta"] == 0
    assert payload["observed_run_complete"] is True
    assert output_path.exists()


def test_compare_app_run_to_human_total_reports_delta(tmp_path):
    human_total_path = tmp_path / "human.json"
    observed_path = tmp_path / "observed.json"
    output_path = tmp_path / "comparison.json"
    human_total_path.write_text(json.dumps({"expected_human_total": 21}), encoding="utf-8")
    observed_path.write_text(json.dumps({"events": [{"event_ts": 1.0}]}), encoding="utf-8")

    payload = compare_app_run_to_human_total(
        human_total_path=human_total_path,
        observed_events_path=observed_path,
        output_path=output_path,
        force=False,
    )

    assert payload["total_matches"] is False
    assert payload["delta"] == -20
