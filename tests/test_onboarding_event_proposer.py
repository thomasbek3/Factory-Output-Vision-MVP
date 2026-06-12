from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.onboarding_event_proposer import (
    GENERATED_BY,
    SCHEMA_VERSION,
    build_event_proposals,
    build_motion_event_proposals_from_samples,
    write_event_proposals,
)
from app.services.stream_recorder import SCHEMA_VERSION as SEGMENT_SCHEMA_VERSION
from app.services.stream_recorder import sha256_file
from scripts import propose_onboarding_events


def _segment(path: str = "/tmp/segment.mp4") -> dict[str, object]:
    return {
        "station_id": "line-a",
        "segment_id": "seg001",
        "path": path,
        "file_size_bytes": 123,
        "sha256": "abc",
        "source_uri_hash": "source-hash",
        "start_wall_ts": "2026-06-09T00:00:00Z",
        "end_wall_ts": "2026-06-09T00:00:06Z",
        "duration_sec": 6.0,
        "codec": "h264",
        "container": "mp4",
        "width": 160,
        "height": 120,
        "fps_estimate": 5.0,
        "decode_ok": True,
        "frame_gaps": [],
        "privacy_mode": "offline_local",
        "pinned_reason": "onboarding_source",
        "probe_error": None,
    }


def test_motion_samples_cluster_into_event_and_stable_negative_proposals() -> None:
    samples = [
        {"timestamp_sec": 0.0, "motion_score": 0.0},
        {"timestamp_sec": 1.0, "motion_score": 0.004},
        {"timestamp_sec": 2.0, "motion_score": 0.08},
        {"timestamp_sec": 2.4, "motion_score": 0.11},
        {"timestamp_sec": 4.8, "motion_score": 0.09},
        {"timestamp_sec": 5.0, "motion_score": 0.003},
    ]

    proposals = build_motion_event_proposals_from_samples(
        station_id="line-a",
        segment=_segment(),
        samples=samples,
        motion_threshold=0.05,
        min_cluster_gap_sec=0.75,
        window_before_sec=1.0,
        window_after_sec=1.0,
        stable_negative_count=1,
    )

    event_proposals = [proposal for proposal in proposals if proposal["candidate_type"] == "event_candidate"]
    negatives = [proposal for proposal in proposals if proposal["candidate_type"] == "hard_negative_candidate"]
    assert [proposal["center_offset_sec"] for proposal in event_proposals] == [2.4, 4.8]
    assert len(negatives) == 1
    for proposal in proposals:
        assert proposal["generated_by"] == GENERATED_BY
        assert proposal["evidence_role"] == "candidate_only_not_truth"
        assert proposal["validation_truth_eligible"] is False
        assert proposal["training_eligible"] is False
        assert proposal["teacher_task"] == "verify_candidate_event"
        assert "frame_diff_or_motion_heatmap" in proposal["required_evidence_packet_assets"]


def test_build_event_proposals_reads_segment_manifest_and_refuses_truth_flags(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    segment_path = tmp_path / "segment.mp4"
    _write_motion_video(segment_path, cv2=cv2, np=np)
    manifest_path = tmp_path / "segment_manifest.json"
    manifest = {
        "schema_version": SEGMENT_SCHEMA_VERSION,
        "station_id": "line-a",
        "source_uri_hash": "source-hash",
        "privacy_mode": "offline_local",
        "segment_seconds": 6,
        "retention_minutes": 30,
        "segments": [
            {
                **_segment(segment_path.as_posix()),
                "file_size_bytes": segment_path.stat().st_size,
                "sha256": sha256_file(segment_path),
            }
        ],
        "updated_at": "2026-06-09T00:00:06Z",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = build_event_proposals(
        segment_manifest_path=manifest_path,
        sample_fps=5.0,
        motion_threshold=0.01,
        min_cluster_gap_sec=0.75,
        window_before_sec=1.0,
        window_after_sec=1.0,
        stable_negative_count=1,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["refuses_validation_truth"] is True
    assert payload["summary"]["event_proposal_count"] >= 1
    assert payload["summary"]["stable_negative_count"] == 1
    assert all(proposal["validation_truth_eligible"] is False for proposal in payload["proposals"])


def test_write_event_proposals_refuses_overwrite_without_force(tmp_path: Path) -> None:
    output = tmp_path / "proposals.json"
    payload = {"schema_version": SCHEMA_VERSION, "summary": {}}
    write_event_proposals(output, payload)

    with pytest.raises(FileExistsError):
        write_event_proposals(output, payload)

    write_event_proposals(output, payload, force=True)


def test_propose_onboarding_events_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = propose_onboarding_events.main(
        ["--segment-manifest", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out.json")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err


def _write_motion_video(path: Path, *, cv2, np) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120))
    if not writer.isOpened():
        pytest.skip("OpenCV cannot write mp4v test video")
    for frame_index in range(30):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        if 8 <= frame_index <= 12:
            x = 20 + ((frame_index - 8) * 8)
            frame[45:75, x : x + 30] = 255
        elif frame_index > 12:
            frame[45:75, 52:82] = 255
        writer.write(frame)
    writer.release()
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip("OpenCV did not write a playable test video")
