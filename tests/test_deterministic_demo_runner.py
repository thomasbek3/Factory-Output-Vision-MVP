from __future__ import annotations

import json
from pathlib import Path

from app.services.deterministic_demo_runner import DeterministicDemoRunner


def _write_report(
    path: Path,
    *,
    video_path: Path,
    calibration_path: Path,
    model_path: Path,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    final_count: int = 2,
) -> None:
    payload = {
        "schema_version": "factory2-runtime-event-audit-v1",
        "video_path": str(video_path),
        "calibration_path": str(calibration_path),
        "model_path": str(model_path),
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "processing_fps": 10.0,
        "video_fps": 30.0,
        "sampled_frame_count": 100,
        "final_count": final_count,
        "elapsed_sec": 1.23,
        "events": [
            {
                "event_ts": 4.0,
                "track_id": 11,
                "reason": "source_token_accepted",
                "count_total": 1,
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "source_track_id": 10,
                "source_token_id": "token-1",
                "chain_id": "chain-1",
                "source_bbox": [0.0, 1.0, 2.0, 3.0],
                "provenance_status": "source_token_authorized",
                "count_authority": "source_token_authorized",
                "predecessor_chain_track_ids": [10],
                "source_observation_count": 3,
                "output_observation_count": 2,
                "gate_decision": None,
            },
            {
                "event_ts": 10.0,
                "track_id": 21,
                "reason": "approved_delivery_chain",
                "count_total": 2,
                "bbox": [5.0, 6.0, 7.0, 8.0],
                "source_track_id": None,
                "source_token_id": None,
                "chain_id": "chain-2",
                "source_bbox": None,
                "provenance_status": "synthetic_approved_chain_token",
                "count_authority": "runtime_inferred_only",
                "predecessor_chain_track_ids": [20],
                "source_observation_count": 0,
                "output_observation_count": 4,
                "gate_decision": None,
            },
        ],
        "track_histories": {},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_runner_uses_explicit_matching_cache_and_reveals_events_by_playback_time(tmp_path: Path) -> None:
    video_path = tmp_path / "factory2.MOV"
    calibration_path = tmp_path / "factory2.json"
    model_path = tmp_path / "panel.pt"
    report_path = tmp_path / "factory2_runtime_event_audit.json"
    for path in (video_path, calibration_path, model_path):
        path.write_text("x", encoding="utf-8")
    _write_report(report_path, video_path=video_path, calibration_path=calibration_path, model_path=model_path)

    runner = DeterministicDemoRunner(cache_path=report_path)
    runner.prepare(video_path=video_path, calibration_path=calibration_path, model_path=model_path)

    assert runner.report_path == report_path.resolve()
    assert runner.receipt_count == 2
    assert runner.expected_final_count == 2
    assert runner.revealed_count == 0

    runner.arm(playback_speed=2.0)
    assert runner.drain_due_events(now_monotonic=10.0) == []

    runner.activate(start_monotonic=10.0)
    assert runner.drain_due_events(now_monotonic=11.9) == []

    first = runner.drain_due_events(now_monotonic=12.0)
    assert [event["track_id"] for event in first] == [11]
    assert first[0]["count_authority"] == "source_token_authorized"
    assert runner.revealed_count == 1
    assert not runner.is_finished

    second = runner.drain_due_events(now_monotonic=15.0)
    assert [event["track_id"] for event in second] == [21]
    assert second[0]["count_authority"] == "runtime_inferred_only"
    assert runner.revealed_count == 2
    assert runner.is_finished


def test_runner_finds_latest_matching_full_video_report_in_report_dir(tmp_path: Path) -> None:
    video_path = tmp_path / "factory2.MOV"
    calibration_path = tmp_path / "factory2.json"
    model_path = tmp_path / "panel.pt"
    for path in (video_path, calibration_path, model_path):
        path.write_text("x", encoding="utf-8")

    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    wrong_report = report_dir / "wrong_runtime_event_audit.json"
    partial_report = report_dir / "partial_runtime_event_audit.json"
    matching_report = report_dir / "matching_runtime_event_audit.json"
    other_video = tmp_path / "other.MOV"
    other_video.write_text("x", encoding="utf-8")

    _write_report(wrong_report, video_path=other_video, calibration_path=calibration_path, model_path=model_path)
    _write_report(
        partial_report,
        video_path=video_path,
        calibration_path=calibration_path,
        model_path=model_path,
        start_seconds=10.0,
        end_seconds=20.0,
    )
    _write_report(matching_report, video_path=video_path, calibration_path=calibration_path, model_path=model_path)

    runner = DeterministicDemoRunner(report_dir=report_dir)
    runner.prepare(video_path=video_path, calibration_path=calibration_path, model_path=model_path)

    assert runner.report_path == matching_report.resolve()
    assert runner.expected_final_count == 2
