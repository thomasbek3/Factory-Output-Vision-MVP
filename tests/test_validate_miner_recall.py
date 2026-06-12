from __future__ import annotations

from datetime import datetime, timedelta

from scripts.validate_miner_recall import build_recall_report, gold_event_wall_time


def test_gold_wall_clock_derives_from_segment_file_and_offset() -> None:
    wall_time = gold_event_wall_time(
        {
            "segment_file": "20260611T152349_20260611T174747Z_e22e5dca.mkv",
            "offset_in_segment_sec": 26.0,
        }
    )

    assert wall_time.strftime("%Y-%m-%d %H:%M:%S") == "2026-06-11 15:24:15"


def test_recall_matching_catches_tolerance_boundary_and_misses_outside() -> None:
    base = datetime(2026, 6, 11, 12, 0, 0)
    gold_events = [
        {"id": "gold-boundary", "wall_time": base},
        {"id": "gold-outside", "wall_time": base + timedelta(minutes=1)},
    ]
    proposals_payload = {
        "summary": {"dropped_low_flash_ratio": 2},
        "proposals": [
            _proposal("candidate-boundary", base + timedelta(seconds=20)),
            _proposal("candidate-outside", base + timedelta(minutes=1, seconds=20.001)),
        ],
    }

    report = build_recall_report(
        proposals_payload=proposals_payload,
        gold_events=gold_events,
        exam_start=base,
        exam_end=base + timedelta(minutes=2),
        match_tolerance_sec=20,
        config={},
    )

    assert [row["caught"] for row in report["gold_results"]] == [True, False]
    assert report["summary"]["caught"] == 1
    assert report["summary"]["dropped_low_flash_ratio"] == 2


def test_recall_gate_passes_at_six_of_seven_and_fails_at_five_of_seven() -> None:
    base = datetime(2026, 6, 11, 12, 0, 0)
    gold_events = [
        {"id": f"gold-{index}", "wall_time": base + timedelta(minutes=index)}
        for index in range(7)
    ]

    pass_report = build_recall_report(
        proposals_payload={"summary": {}, "proposals": [_proposal(f"candidate-{index}", event["wall_time"]) for index, event in enumerate(gold_events[:6])]},
        gold_events=gold_events,
        exam_start=base,
        exam_end=base + timedelta(minutes=6),
        match_tolerance_sec=20,
        config={},
    )
    fail_report = build_recall_report(
        proposals_payload={"summary": {}, "proposals": [_proposal(f"candidate-{index}", event["wall_time"]) for index, event in enumerate(gold_events[:5])]},
        gold_events=gold_events,
        exam_start=base,
        exam_end=base + timedelta(minutes=6),
        match_tolerance_sec=20,
        config={},
    )

    assert pass_report["summary"]["caught"] == 6
    assert pass_report["verdict"] == "PASS"
    assert fail_report["summary"]["caught"] == 5
    assert fail_report["verdict"] == "FAIL"
    assert "layer-2 state-change miner" in fail_report["failure_next_step"]


def _proposal(candidate_id: str, center_time: datetime) -> dict[str, object]:
    segment_start = center_time.replace(microsecond=0)
    return {
        "candidate_id": candidate_id,
        "candidate_type": "event_candidate",
        "segment_path": f"/tmp/{segment_start.strftime('%Y%m%dT%H%M%S')}_test.mkv",
        "center_offset_sec": (center_time - segment_start).total_seconds(),
    }
