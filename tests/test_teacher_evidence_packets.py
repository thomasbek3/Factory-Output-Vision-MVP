from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.onboarding_event_proposer import SCHEMA_VERSION as EVENT_PROPOSAL_SCHEMA_VERSION
from app.services.teacher_evidence_packets import SCHEMA_VERSION, build_teacher_evidence_packets
from scripts import build_teacher_evidence_packets as build_teacher_evidence_packets_cli


def test_build_teacher_evidence_packets_writes_assets_and_manifest(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    segment_path = tmp_path / "segment.mp4"
    _write_motion_video(segment_path, cv2=cv2, np=np)
    proposals_path = tmp_path / "event_proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "schema_version": EVENT_PROPOSAL_SCHEMA_VERSION,
                "station_id": "line-a",
                "privacy_mode": "offline_local",
                "proposals": [_proposal(segment_path)],
            }
        ),
        encoding="utf-8",
    )

    payload = build_teacher_evidence_packets(
        event_proposals_path=proposals_path,
        output_dir=tmp_path / "packets",
        sequence_fps=2.0,
        max_packets=1,
        max_width=320,
        force=True,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["refuses_validation_truth"] is True
    assert payload["packet_count"] == 1
    packet = payload["packets"][0]
    packet_manifest = json.loads(Path(packet["packet_manifest_path"]).read_text(encoding="utf-8"))
    assert packet_manifest["teacher_task"] == "verify_candidate_event"
    assert packet_manifest["validation_truth_eligible"] is False
    assert packet_manifest["training_eligible"] is False
    kinds = {asset["kind"] for asset in packet_manifest["assets"]}
    assert {
        "event_clip",
        "before_full_frame",
        "during_full_frame",
        "after_full_frame",
        "frame_diff_or_motion_heatmap",
        "output_zone_crop_sequence",
        "stack_crop_sequence",
    } <= kinds
    for asset in packet_manifest["assets"]:
        asset_path = Path(asset["path"])
        assert asset_path.exists()
        assert asset_path.stat().st_size > 0


def test_build_teacher_evidence_packets_uses_output_zone_crop(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    segment_path = tmp_path / "segment.mp4"
    _write_motion_video(segment_path, cv2=cv2, np=np)
    proposals_path = tmp_path / "event_proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "schema_version": EVENT_PROPOSAL_SCHEMA_VERSION,
                "station_id": "line-a",
                "privacy_mode": "offline_local",
                "proposals": [_proposal(segment_path)],
            }
        ),
        encoding="utf-8",
    )
    polygon = [[0.50, 0.25], [0.75, 0.25], [0.75, 0.75], [0.50, 0.75]]

    payload = build_teacher_evidence_packets(
        event_proposals_path=proposals_path,
        output_dir=tmp_path / "packets",
        sequence_fps=2.0,
        max_packets=1,
        max_width=320,
        output_zone_polygon=polygon,
        force=True,
    )

    packet_manifest = json.loads(Path(payload["packets"][0]["packet_manifest_path"]).read_text(encoding="utf-8"))
    assert packet_manifest["crop_source"] == "station_calibration_output_zone"
    crop_asset = next(asset for asset in packet_manifest["assets"] if asset["kind"] == "output_zone_crop_sequence")
    crop = cv2.imread(crop_asset["path"])
    assert crop is not None
    expected_height, expected_width = _expected_crop_shape(width=160, height=120, polygon=polygon)
    assert crop.shape[:2] == (expected_height, expected_width)


def test_build_teacher_evidence_packets_refuses_overwrite_without_force(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    segment_path = tmp_path / "segment.mp4"
    _write_motion_video(segment_path, cv2=cv2, np=np)
    proposals_path = tmp_path / "event_proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "schema_version": EVENT_PROPOSAL_SCHEMA_VERSION,
                "station_id": "line-a",
                "privacy_mode": "offline_local",
                "proposals": [_proposal(segment_path)],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "packets"

    build_teacher_evidence_packets(
        event_proposals_path=proposals_path,
        output_dir=output_dir,
        sequence_fps=2.0,
        max_packets=1,
        max_width=320,
        force=True,
    )

    with pytest.raises(FileExistsError):
        build_teacher_evidence_packets(
            event_proposals_path=proposals_path,
            output_dir=output_dir,
            sequence_fps=2.0,
            max_packets=1,
            max_width=320,
            force=False,
        )


def test_build_teacher_evidence_packets_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = build_teacher_evidence_packets_cli.main(
        ["--event-proposals", str(tmp_path / "missing.json"), "--output-dir", str(tmp_path / "packets")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err


def _proposal(segment_path: Path) -> dict[str, object]:
    return {
        "station_id": "line-a",
        "candidate_id": "seg001_motion_0001",
        "window_id": "seg001_motion_0001",
        "segment_id": "seg001",
        "segment_path": segment_path.as_posix(),
        "candidate_type": "event_candidate",
        "proposal_type": "motion_burst",
        "candidate_reasons": ["frame_motion_above_threshold"],
        "start_offset_sec": 1.0,
        "center_offset_sec": 2.0,
        "end_offset_sec": 3.0,
        "duration_sec": 2.0,
        "label_status": "unreviewed",
        "label_authority_tier": "bronze",
        "evidence_role": "candidate_only_not_truth",
        "validation_truth_eligible": False,
        "training_eligible": False,
        "motion_summary": {
            "peak_motion_score": 0.2,
            "stable_before_sec": 1.0,
            "stable_after_sec": 3.0,
        },
    }


def _write_motion_video(path: Path, *, cv2, np) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120))
    if not writer.isOpened():
        pytest.skip("OpenCV cannot write mp4v test video")
    for frame_index in range(25):
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


def _expected_crop_shape(*, width: int, height: int, polygon: list[list[float]]) -> tuple[int, int]:
    xs = [point[0] * float(width - 1) for point in polygon]
    ys = [point[1] * float(height - 1) for point in polygon]
    margin_x = (max(xs) - min(xs)) * 0.10
    margin_y = (max(ys) - min(ys)) * 0.10
    left = max(0, round(min(xs) - margin_x))
    right = min(width, round(max(xs) + margin_x) + 1)
    top = max(0, round(min(ys) - margin_y))
    bottom = min(height, round(max(ys) + margin_y) + 1)
    return bottom - top, right - left
