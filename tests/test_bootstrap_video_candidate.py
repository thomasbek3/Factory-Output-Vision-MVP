from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.bootstrap_video_candidate import (
    build_candidate_manifest,
    build_next_steps,
    build_total_payload,
    metadata_from_ffprobe,
    write_truth_template,
)


def test_metadata_from_ffprobe_extracts_primary_video_stream() -> None:
    metadata = metadata_from_ffprobe(
        {
            "format": {"duration": "12.5"},
            "streams": [
                {"codec_type": "audio", "codec_name": "aac"},
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30/1",
                    "nb_frames": "375",
                },
            ],
        }
    )

    assert metadata == {
        "duration_sec": 12.5,
        "width": 1920,
        "height": 1080,
        "codec": "hevc",
        "fps": "30/1",
        "frame_count": 375,
    }


def test_build_total_payload_keeps_total_provisional() -> None:
    payload = build_total_payload(
        video_path=Path("demo/new.mov"),
        video_sha256="abc",
        metadata={"duration_sec": 10.0},
        expected_total=7,
        human_counter="Thomas",
        truth_rule_id="rule",
        count_rule="count rule",
        today=date(2026, 5, 2),
    )

    assert payload["expected_human_total"] == 7
    assert payload["verification_status"] == "provisional_total_only"
    assert payload["timestamp_truth_status"] == "not_reviewed_yet"
    assert "reviewed timestamp truth" in payload["validation_note"]


def test_build_candidate_manifest_copies_baseline_runtime_but_stays_candidate() -> None:
    manifest = build_candidate_manifest(
        case_id="new_case",
        display_name="New Case",
        video_path=Path("demo/new.mov"),
        video_sha256="abc",
        metadata={"duration_sec": 10.0, "width": 1920, "height": 1080, "codec": "hevc"},
        expected_total=7,
        truth_rule_id="rule",
        count_rule="count rule",
        human_total_path=Path("data/reports/new_total.json"),
        truth_ledger_path=Path("data/reports/new_ledger.json"),
        baseline_manifest={
            "runtime": {
                "demo_count_mode": "live_reader_snapshot",
                "counting_mode": "event_based",
                "model_path": "models/baseline.pt",
                "event_track_max_match_distance": 260.0,
            }
        },
    )

    assert manifest["status"] == "candidate"
    assert manifest["truth"]["expected_total"] == 7
    assert manifest["runtime"]["model_path"] == "models/baseline.pt"
    assert manifest["runtime"]["event_track_max_match_distance"] == 260.0


def test_write_truth_template_creates_pending_rows(tmp_path: Path) -> None:
    output = tmp_path / "truth.csv"

    write_truth_template(output, case_id="new_case", expected_total=2)

    assert output.read_text(encoding="utf-8").splitlines() == [
        "truth_event_id,count_total,event_ts,notes",
        "new_case-truth-0001,1,,pending reviewed timestamp",
        "new_case-truth-0002,2,,pending reviewed timestamp",
    ]


def test_next_steps_encode_fast_path_gates() -> None:
    steps = build_next_steps(
        case_id="new_case",
        video_path=Path("demo/new.mov"),
        expected_total=7,
        baseline_case_id="img2628_candidate",
    )

    assert any("detector transfer screen" in step for step in steps)
    assert any("Only run the visible 1.0x dashboard proof" in step for step in steps)
    assert any("final total matches but event diff has swaps" in step for step in steps)
