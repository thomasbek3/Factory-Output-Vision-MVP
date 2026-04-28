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


def test_select_representative_observations_keeps_first_mid_last() -> None:
    observations = [{"timestamp": idx} for idx in range(7)]

    assert diag.select_representative_observations(observations) == [
        {"timestamp": 0},
        {"timestamp": 3},
        {"timestamp": 6},
    ]


def test_build_track_evidence_preserves_representative_observations() -> None:
    evidence = diag.build_track_evidence(
        track_points={1: [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]},
        track_motion={1: [0.1, 0.2, 0.3, 0.4]},
        track_zones={1: ["source", "source", "output", "output"]},
        track_times={1: [1.0, 2.0, 3.0, 4.0]},
        track_detections={1: 4},
        track_person_overlaps={1: [0.0, 0.1]},
        track_observations={1: [{"timestamp": idx, "box_xywh": [idx, idx, 10, 10]} for idx in range(4)]},
    )[0]

    assert evidence.observations == [
        {"timestamp": 0, "box_xywh": [0, 0, 10, 10]},
        {"timestamp": 2, "box_xywh": [2, 2, 10, 10]},
        {"timestamp": 3, "box_xywh": [3, 3, 10, 10]},
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
    assert result["hard_negative_manifest_path"] == str(out_dir / "hard_negative_manifest.json")
    hard_negative_manifest = json.loads((out_dir / "hard_negative_manifest.json").read_text(encoding="utf-8"))
    assert hard_negative_manifest["schema_version"] == "factory-hard-negative-manifest-v1"
    assert hard_negative_manifest["count"] == 1
    assert hard_negative_manifest["items"][0]["track_id"] == 1
    assert hard_negative_manifest["items"][0]["label"] == "hard_negative"
    assert hard_negative_manifest["items"][0]["reason"] == "static_stack_edge"
    assert hard_negative_manifest["items"][0]["assets"]["track_sheet_path"] == str(out_dir / "track_receipts" / "track-000001-sheet.jpg")
    receipt = json.loads((out_dir / "track_receipts" / "track-000001.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "factory-track-receipt-v1"
    assert receipt["diagnosis"]["reason"] == "static_stack_edge"
    assert receipt["perception_gate"]["reason"] == "static_stack_edge"
    assert receipt["review_assets"]["track_sheet_path"] == str(out_dir / "track_receipts" / "track-000001-sheet.jpg")
    assert (out_dir / "track_receipts" / "track-000001-sheet.jpg").read_bytes() == b"fake jpg"
    assert json.loads((out_dir / "diagnostic.json").read_text(encoding="utf-8")) == result

    with pytest.raises(FileExistsError, match="--force"):
        diag.prepare_output_dir(out_dir, force=False)


def test_refresh_diagnostic_gate_receipts_promotes_track_from_person_panel_sidecar(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (receipts_dir / "track-000005-sheet.jpg").write_bytes(b"fake jpg")
    crop_dir = receipts_dir / "track-000005-crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    (crop_dir / "crop-01-source.jpg").write_bytes(b"fake crop")

    track_receipt = receipts_dir / "track-000005.json"
    track_receipt.write_text(
        json.dumps(
            {
                "schema_version": "factory-track-receipt-v1",
                "track_id": 5,
                "timestamps": {"first": 80.0, "last": 110.0},
                "evidence": {
                    "track_id": 5,
                    "first_timestamp": 80.0,
                    "last_timestamp": 110.0,
                    "first_zone": "source",
                    "zones_seen": ["source", "output"],
                    "source_frames": 38,
                    "output_frames": 1,
                    "max_displacement": 603.294,
                    "mean_internal_motion": 0.337425,
                    "max_internal_motion": 0.730217,
                    "detections": 39,
                    "static_location_ratio": 0.333333,
                    "flow_coherence": 0.501419,
                    "static_stack_overlap_ratio": 0.0,
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 0.0,
                    "observations": [],
                },
                "diagnosis": {
                    "track_id": 5,
                    "decision": "candidate",
                    "reason": "source_to_output_motion",
                    "flags": [],
                    "evidence": {"track_id": 5},
                },
                "perception_gate": {
                    "track_id": 5,
                    "decision": "reject",
                    "reason": "worker_body_overlap",
                    "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                    "evidence": {
                        "track_id": 5,
                        "source_frames": 38,
                        "output_frames": 1,
                        "zones_seen": ["source", "output"],
                        "first_zone": "source",
                        "max_displacement": 603.294,
                        "mean_internal_motion": 0.337425,
                        "max_internal_motion": 0.730217,
                        "detections": 39,
                        "person_overlap_ratio": 1.0,
                        "outside_person_ratio": 0.0,
                        "static_stack_overlap_ratio": 0.0,
                        "static_location_ratio": 0.333333,
                        "flow_coherence": 0.501419,
                        "edge_like_ratio": 0.0,
                    },
                },
                "review_assets": {
                    "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                    "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                    "track_sheet_path": str(receipts_dir / "track-000005-sheet.jpg"),
                    "raw_crop_paths": [str(crop_dir / "crop-01-source.jpg")],
                },
            }
        ),
        encoding="utf-8",
    )
    track_receipt.with_name("track-000005-person-panel-separation.json").write_text(
        json.dumps(
            {
                "packet_id": "event0002-track000005",
                "diagnostic_only": True,
                "recommendation": "countable_panel_candidate",
                "summary": {
                    "frame_count": 3,
                    "separable_panel_candidate_frames": 3,
                    "worker_body_overlap_frames": 0,
                    "static_or_background_edge_frames": 0,
                    "max_visible_nonperson_ratio": 0.542531,
                    "max_estimated_visible_signal": 0.075512,
                },
                "selected_frames": [
                    {"zone": "source", "separation_decision": "separable_panel_candidate"},
                    {"zone": "source", "separation_decision": "separable_panel_candidate"},
                    {"zone": "output", "separation_decision": "separable_panel_candidate"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")
    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "calibration_path": "data/calibration/factory2_ai_only_v1_no_gate.json",
                "start_timestamp": 78.0,
                "end_timestamp": 118.0,
                "fps": 3.0,
                "model_path": None,
                "person_model_path": None,
                "confidence": 0.2,
                "frame_count": 120,
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "track_receipts": [str(track_receipt)],
                "track_receipt_cards": [str(receipts_dir / "track-000005-sheet.jpg")],
                "hard_negative_manifest_path": str(out_dir / "hard_negative_manifest.json"),
                "diagnosis": [
                    {
                        "track_id": 5,
                        "decision": "candidate",
                        "reason": "source_to_output_motion",
                        "flags": [],
                        "evidence": {"track_id": 5},
                    }
                ],
                "summary": {
                    "track_count": 1,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 0},
                    "reason_counts": {"source_to_output_motion": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    {
                        "track_id": 5,
                        "decision": "reject",
                        "reason": "worker_body_overlap",
                        "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                        "evidence": {
                            "track_id": 5,
                            "source_frames": 38,
                            "output_frames": 1,
                            "zones_seen": ["source", "output"],
                            "first_zone": "source",
                            "max_displacement": 603.294,
                            "mean_internal_motion": 0.337425,
                            "max_internal_motion": 0.730217,
                            "detections": 39,
                            "person_overlap_ratio": 1.0,
                            "outside_person_ratio": 0.0,
                            "static_stack_overlap_ratio": 0.0,
                            "static_location_ratio": 0.333333,
                            "flow_coherence": 0.501419,
                            "edge_like_ratio": 0.0,
                        },
                    }
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 1,
                    "decision_counts": {"allow_source_token": 0, "reject": 1, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    assert result["perception_gate"][0]["decision"] == "allow_source_token"
    assert result["perception_gate"][0]["reason"] == "moving_panel_candidate"
    assert result["perception_gate_summary"]["allowed_source_token_tracks"] == [5]
    refreshed_receipt = json.loads(track_receipt.read_text(encoding="utf-8"))
    assert refreshed_receipt["perception_gate"]["decision"] == "allow_source_token"
    assert refreshed_receipt["perception_gate"]["reason"] == "moving_panel_candidate"
    assert refreshed_receipt["review_assets"]["track_sheet_path"] == str(receipts_dir / "track-000005-sheet.jpg")
    assert refreshed_receipt["review_assets"]["raw_crop_paths"] == [str(crop_dir / "crop-01-source.jpg")]
    assert result["hard_negative_manifest_path"] is None
    assert not (out_dir / "hard_negative_manifest.json").exists()


def test_refresh_diagnostic_gate_receipts_preserves_zero_outside_person_ratio(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    track_receipt = receipts_dir / "track-000001.json"
    track_receipt.write_text(
        json.dumps(
            {
                "schema_version": "factory-track-receipt-v1",
                "track_id": 1,
                "timestamps": {"first": 370.0, "last": 391.0},
                "evidence": {
                    "track_id": 1,
                    "first_timestamp": 370.0,
                    "last_timestamp": 391.0,
                    "first_zone": "source",
                    "zones_seen": ["source", "output"],
                    "source_frames": 35,
                    "output_frames": 2,
                    "max_displacement": 456.787,
                    "mean_internal_motion": 0.24737,
                    "max_internal_motion": 0.610074,
                    "detections": 37,
                    "static_location_ratio": 0.27027,
                    "flow_coherence": 0.465985,
                    "static_stack_overlap_ratio": 0.0,
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 0.0,
                    "observations": [],
                },
                "diagnosis": {
                    "track_id": 1,
                    "decision": "candidate",
                    "reason": "source_to_output_motion",
                    "flags": [],
                    "evidence": {"track_id": 1},
                },
                "review_assets": {
                    "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                    "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                    "track_sheet_path": None,
                    "raw_crop_paths": [],
                },
            }
        ),
        encoding="utf-8",
    )
    track_receipt.with_name("track-000001-person-panel-separation.json").write_text(
        json.dumps(
            {
                "packet_id": "event0006-track000001",
                "diagnostic_only": True,
                "recommendation": "insufficient_visibility",
                "summary": {
                    "frame_count": 3,
                    "separable_panel_candidate_frames": 1,
                    "worker_body_overlap_frames": 1,
                    "static_or_background_edge_frames": 0,
                    "max_visible_nonperson_ratio": 0.822163,
                    "max_estimated_visible_signal": 0.028576,
                },
                "selected_frames": [
                    {"zone": "source", "separation_decision": "worker_body_overlap"},
                    {"zone": "source", "separation_decision": "separable_panel_candidate"},
                    {"zone": "output", "separation_decision": "insufficient_visibility"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")
    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 370.0,
                "end_timestamp": 410.0,
                "fps": 3.0,
                "track_receipts": [str(track_receipt)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {
                        "track_id": 1,
                        "decision": "candidate",
                        "reason": "source_to_output_motion",
                        "flags": [],
                        "evidence": {"track_id": 1},
                    }
                ],
                "summary": {
                    "track_count": 1,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 0},
                    "reason_counts": {"source_to_output_motion": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    {
                        "track_id": 1,
                        "decision": "reject",
                        "reason": "worker_body_overlap",
                        "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                        "evidence": {
                            "track_id": 1,
                            "source_frames": 35,
                            "output_frames": 2,
                            "zones_seen": ["source", "output"],
                            "first_zone": "source",
                            "max_displacement": 456.787,
                            "mean_internal_motion": 0.24737,
                            "max_internal_motion": 0.610074,
                            "detections": 37,
                            "person_overlap_ratio": 1.0,
                            "outside_person_ratio": 0.0,
                            "static_stack_overlap_ratio": 0.0,
                            "static_location_ratio": 0.27027,
                            "flow_coherence": 0.465985,
                            "edge_like_ratio": 0.0,
                        },
                    }
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 1,
                    "decision_counts": {"allow_source_token": 0, "reject": 1, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    assert result["perception_gate"][0]["decision"] == "reject"
    assert result["perception_gate"][0]["reason"] == "worker_body_overlap"
    assert result["perception_gate"][0]["evidence"]["outside_person_ratio"] == 0.0


def test_refresh_diagnostic_gate_receipts_uses_existing_gate_row_as_baseline(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    track_receipt = receipts_dir / "track-000004.json"
    track_receipt.write_text(
        json.dumps(
            {
                "schema_version": "factory-track-receipt-v1",
                "track_id": 4,
                "timestamps": {"first": 372.0, "last": 390.0},
                "evidence": {
                    "track_id": 4,
                    "first_timestamp": 372.0,
                    "last_timestamp": 390.0,
                    "first_zone": "source",
                    "zones_seen": ["source", "output"],
                    "source_frames": 33,
                    "output_frames": 3,
                    "max_displacement": 482.653,
                    "mean_internal_motion": 0.270206,
                    "max_internal_motion": 0.590582,
                    "detections": 36,
                    "static_location_ratio": 0.416667,
                    "flow_coherence": 0.222248,
                    "static_stack_overlap_ratio": 0.0,
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 1.0,
                    "observations": [],
                },
                "diagnosis": {
                    "track_id": 4,
                    "decision": "candidate",
                    "reason": "source_to_output_motion",
                    "flags": [],
                    "evidence": {"track_id": 4},
                },
                "review_assets": {
                    "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                    "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                    "track_sheet_path": None,
                    "raw_crop_paths": [],
                },
            }
        ),
        encoding="utf-8",
    )
    track_receipt.with_name("track-000004-person-panel-separation.json").write_text(
        json.dumps(
            {
                "packet_id": "event0006-track000004",
                "diagnostic_only": True,
                "recommendation": "insufficient_visibility",
                "summary": {
                    "frame_count": 3,
                    "separable_panel_candidate_frames": 1,
                    "worker_body_overlap_frames": 2,
                    "static_or_background_edge_frames": 0,
                    "max_visible_nonperson_ratio": 0.760976,
                    "max_estimated_visible_signal": 0.0456,
                },
                "selected_frames": [
                    {"zone": "source", "separation_decision": "worker_body_overlap"},
                    {"zone": "source", "separation_decision": "worker_body_overlap"},
                    {"zone": "output", "separation_decision": "separable_panel_candidate"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")
    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 370.0,
                "end_timestamp": 410.0,
                "fps": 3.0,
                "track_receipts": [str(track_receipt)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {
                        "track_id": 4,
                        "decision": "candidate",
                        "reason": "source_to_output_motion",
                        "flags": [],
                        "evidence": {"track_id": 4},
                    }
                ],
                "summary": {
                    "track_count": 1,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 0},
                    "reason_counts": {"source_to_output_motion": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    {
                        "track_id": 4,
                        "decision": "reject",
                        "reason": "worker_body_overlap",
                        "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                        "evidence": {
                            "track_id": 4,
                            "source_frames": 33,
                            "output_frames": 3,
                            "zones_seen": ["source", "output"],
                            "first_zone": "source",
                            "max_displacement": 482.653,
                            "mean_internal_motion": 0.270206,
                            "max_internal_motion": 0.590582,
                            "detections": 36,
                            "person_overlap_ratio": 1.0,
                            "outside_person_ratio": 0.0,
                            "static_stack_overlap_ratio": 0.0,
                            "static_location_ratio": 0.416667,
                            "flow_coherence": 0.222248,
                            "edge_like_ratio": 0.0,
                        },
                    }
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 1,
                    "decision_counts": {"allow_source_token": 0, "reject": 1, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    assert result["perception_gate"][0]["decision"] == "reject"
    assert result["perception_gate"][0]["reason"] == "worker_body_overlap"
    assert result["perception_gate"][0]["evidence"]["outside_person_ratio"] == 0.0
