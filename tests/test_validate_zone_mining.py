from __future__ import annotations

import json
from pathlib import Path

from scripts.research.factory2.run_factory_day1_pipeline import cap_event_proposals, exclude_segments_by_filename_window
from scripts.research.factory2.validate_zone_mining import build_zone_mining_validation, proposal_wall_time


def test_proposal_wall_time_uses_segment_filename_start() -> None:
    wall_time = proposal_wall_time(
        {
            "segment_path": "/tmp/20260611T134700_rec001.mkv",
            "center_offset_sec": 12.5,
        }
    )

    assert wall_time is not None
    assert wall_time.strftime("%H:%M:%S") == "13:47:12"


def test_validate_zone_mining_passes_when_top_candidates_hit_growth_windows(tmp_path: Path) -> None:
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(
        json.dumps({"proposals": _events([("20260611T134700", index, 1.0 - (index * 0.01)) for index in range(12)])
                    + _events([("20260611T122600", index, 0.7 - (index * 0.01)) for index in range(2)])
                    + _events([("20260611T111000", index, 0.4 - (index * 0.01)) for index in range(6)])}),
        encoding="utf-8",
    )

    report = build_zone_mining_validation(
        proposals_path=proposals_path,
        growth_windows=[["12:26", "13:05"], ["13:47", "16:27"]],
        stall_windows=[["13:05", "13:47"]],
        date_text="2026-06-11",
        top_n=20,
    )

    assert report["verdict"] == "PASS"
    assert report["summary"]["growth_window_count"] == 14
    assert report["summary"]["heavy_growth_window_count"] == 12
    assert report["summary"]["stall_window_count"] == 0


def test_validate_zone_mining_fails_when_stall_window_has_top_candidate(tmp_path: Path) -> None:
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(
        json.dumps({"proposals": _events([("20260611T130600", 0, 0.99)])
                    + _events([("20260611T134700", index, 0.9 - (index * 0.01)) for index in range(12)])}),
        encoding="utf-8",
    )

    report = build_zone_mining_validation(
        proposals_path=proposals_path,
        growth_windows=[["12:26", "13:05"], ["13:47", "16:27"]],
        stall_windows=[["13:05", "13:47"]],
        date_text="2026-06-11",
        top_n=13,
    )

    assert report["verdict"] == "FAIL"
    assert report["summary"]["stall_window_count"] == 1


def test_validate_zone_mining_uses_single_growth_window_as_heavy_growth(tmp_path: Path) -> None:
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(
        json.dumps({"proposals": _events([("20260611T134700", index, 1.0 - (index * 0.01)) for index in range(10)])}),
        encoding="utf-8",
    )

    report = build_zone_mining_validation(
        proposals_path=proposals_path,
        growth_windows=[["13:47", "16:27"]],
        stall_windows=[["13:05", "13:47"]],
        date_text="2026-06-11",
        top_n=10,
    )

    assert report["verdict"] == "PASS"
    assert report["summary"]["growth_window_count"] == 10
    assert report["summary"]["heavy_growth_window_count"] == 10


def test_zone_ranked_cap_keeps_top_scores_with_twelve_second_dedup(tmp_path: Path) -> None:
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "proposals": [
                    _event("a", "2026-06-11T14:00:00Z", 0.0, 0.90),
                    _event("b", "2026-06-11T14:00:00Z", 13.0, 0.80),
                    _event("c", "2026-06-11T14:00:00Z", 25.0, 0.70),
                    _event("d", "2026-06-11T14:01:00Z", 0.0, 0.60),
                    _event("e", "2026-06-11T14:02:00Z", 0.0, 0.50),
                ],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )

    summary = cap_event_proposals(
        proposals_path,
        max_events=3,
        proposal_mode="output_zone_motion",
        teacher_negative_cap=30,
    )

    payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    assert summary["events_kept"] == 3
    assert [row["candidate_id"] for row in payload["proposals"]] == ["a", "b", "d"]
    assert payload["summary"]["day1_event_cap"]["sampling"] == "top_n_zone_score_time_dedup"


def test_pipeline_segment_exclusion_drops_only_inclusive_filename_range() -> None:
    segments = [
        {"segment_id": "before", "path": "/tmp/20260611T152149_a.mkv"},
        {"segment_id": "start", "path": "/tmp/20260611T152150_a.mkv"},
        {"segment_id": "middle", "path": "/tmp/20260611T160000_a.mkv"},
        {"segment_id": "end", "path": "/tmp/20260611T162733_a.mkv"},
        {"segment_id": "after", "path": "/tmp/20260611T162734_a.mkv"},
    ]

    kept, dropped = exclude_segments_by_filename_window(
        segments,
        exclude_segments_after="20260611T152150",
        exclude_segments_before="20260611T162733",
    )

    assert dropped == 3
    assert [row["segment_id"] for row in kept] == ["before", "after"]


def _events(rows: list[tuple[str, int, float]]) -> list[dict[str, object]]:
    return [
        {
            "candidate_id": f"{start}_{index}",
            "segment_path": f"/tmp/{start}_rec001.mkv",
            "center_offset_sec": float(index),
            "candidate_type": "event_candidate",
            "peak_motion_score_output_zone": score,
        }
        for start, index, score in rows
    ]


def _event(candidate_id: str, start_wall_ts: str, center_offset_sec: float, score: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "window_id": candidate_id,
        "segment_path": f"/tmp/20260611T140000_{candidate_id}.mkv",
        "source_start_wall_ts": start_wall_ts,
        "center_offset_sec": center_offset_sec,
        "candidate_type": "event_candidate",
        "peak_motion_score_output_zone": score,
    }
