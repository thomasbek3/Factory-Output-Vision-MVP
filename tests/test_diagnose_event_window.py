from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import diagnose_event_window as diag


def test_classify_track_rejects_output_only_low_motion_static_edge() -> None:
    track = diag.TrackEvidence(
        track_id=7,
        first_timestamp=10.0,
        last_timestamp=14.0,
        first_zone="output",
        zones_seen=["output"],
        source_frames=0,
        output_frames=5,
        max_displacement=3.0,
        mean_internal_motion=0.01,
        max_internal_motion=0.02,
        detections=5,
    )

    result = diag.classify_track_evidence(
        track,
        min_displacement=25.0,
        min_internal_motion=0.08,
    )

    assert result.decision == "reject"
    assert result.reason == "static_stack_edge"
    assert "output_only_no_source_token" in result.flags


def test_classify_track_marks_source_to_output_motion_as_transfer_candidate() -> None:
    track = diag.TrackEvidence(
        track_id=3,
        first_timestamp=20.0,
        last_timestamp=26.0,
        first_zone="source",
        zones_seen=["source", "transfer", "output"],
        source_frames=3,
        output_frames=2,
        max_displacement=180.0,
        mean_internal_motion=0.14,
        max_internal_motion=0.32,
        detections=6,
    )

    result = diag.classify_track_evidence(
        track,
        min_displacement=25.0,
        min_internal_motion=0.08,
    )

    assert result.decision == "candidate"
    assert result.reason == "source_to_output_motion"
    assert result.flags == []


def test_select_track_overlay_frames_uses_first_mid_last_timestamps(tmp_path: Path) -> None:
    frames = [tmp_path / f"overlay_{idx:06d}.jpg" for idx in range(1, 11)]
    track = diag.TrackEvidence(
        track_id=1,
        first_timestamp=102.0,
        last_timestamp=108.0,
        first_zone="source",
        zones_seen=["source", "output"],
        source_frames=2,
        output_frames=2,
        max_displacement=100.0,
        mean_internal_motion=0.2,
        max_internal_motion=0.4,
        detections=4,
    )

    selected = diag.select_track_overlay_frames(track=track, overlay_frames=frames, start_timestamp=100.0, fps=1.0)

    assert selected == [
        ("first/source-ish", frames[2]),
        ("mid/high-evidence", frames[5]),
        ("last/output-ish", frames[8]),
    ]


def test_diagnose_event_window_writes_manifest_and_refuses_overwrite(tmp_path: Path) -> None:
    video = tmp_path / "factory2.MOV"
    video.write_text("not video", encoding="utf-8")
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "source_polygons": [[[60, 0], [100, 0], [100, 100], [60, 100]]],
                "output_polygons": [[[0, 0], [40, 0], [40, 100], [0, 100]]],
                "ignore_polygons": [],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "diagnostic"

    frames = [tmp_path / f"frame_{idx}.jpg" for idx in range(3)]
    for frame in frames:
        frame.write_text("frame", encoding="utf-8")

    def fake_extract_frames(**kwargs):
        target = kwargs["frames_dir"]
        target.mkdir(parents=True, exist_ok=True)
        copied = []
        for idx, frame in enumerate(frames, start=1):
            dest = target / f"frame_{idx:06d}.jpg"
            dest.write_text(frame.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(dest)
        return copied

    def fake_analyze(**kwargs):
        overlay_dir = kwargs["overlay_dir"]
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay = overlay_dir / "overlay_000001.jpg"
        overlay.write_text("overlay", encoding="utf-8")
        evidence = diag.TrackEvidence(
            track_id=1,
            first_timestamp=kwargs["start_timestamp"],
            last_timestamp=kwargs["start_timestamp"] + 1,
            first_zone="output",
            zones_seen=["output"],
            source_frames=0,
            output_frames=2,
            max_displacement=1.0,
            mean_internal_motion=0.01,
            max_internal_motion=0.01,
            detections=2,
        )
        return diag.AnalysisArtifacts(
            track_evidence=[evidence],
            overlay_frames=[overlay],
            frame_count=3,
        )

    def fake_media(**kwargs):
        kwargs["sheet_path"].write_text("sheet", encoding="utf-8")
        kwargs["video_path"].write_text("video", encoding="utf-8")

    def fake_receipt_card(**kwargs):
        path = kwargs["output_path"]
        path.write_bytes(b"fake jpg")
        return path

    result = diag.diagnose_event_window(
        video_path=video,
        calibration_path=calibration,
        out_dir=out_dir,
        start_timestamp=10.0,
        end_timestamp=14.0,
        fps=5.0,
        model_path=None,
        confidence=0.2,
        force=False,
        frame_extractor=fake_extract_frames,
        analyzer=fake_analyze,
        media_maker=fake_media,
        receipt_card_maker=fake_receipt_card,
    )

    assert result["schema_version"] == "factory-event-diagnostic-v1"
    assert result["diagnosis"][0]["decision"] == "reject"
    assert result["diagnosis"][0]["reason"] == "static_stack_edge"
    assert result["overlay_sheet_path"].endswith("overlay_sheet.jpg")
    assert result["track_receipts"] == [str(out_dir / "track_receipts" / "track-000001.json")]
    assert result["track_receipt_cards"] == [str(out_dir / "track_receipts" / "track-000001-sheet.jpg")]
    receipt = json.loads((out_dir / "track_receipts" / "track-000001.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "factory-track-receipt-v1"
    assert receipt["diagnosis"]["reason"] == "static_stack_edge"
    assert receipt["perception_gate"]["reason"] == "static_stack_edge"
    assert receipt["review_assets"]["track_sheet_path"] == str(out_dir / "track_receipts" / "track-000001-sheet.jpg")
    assert (out_dir / "track_receipts" / "track-000001-sheet.jpg").read_bytes() == b"fake jpg"
    assert json.loads((out_dir / "diagnostic.json").read_text(encoding="utf-8")) == result

    with pytest.raises(FileExistsError, match="--force"):
        diag.prepare_output_dir(out_dir, force=False)
