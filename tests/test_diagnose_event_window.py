from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import diagnose_event_window as diag


def _track_receipt_payload(
    *,
    track_id: int,
    first_timestamp: float,
    last_timestamp: float,
    first_zone: str,
    zones_seen: list[str],
    source_frames: int,
    output_frames: int,
    max_displacement: float,
    mean_internal_motion: float,
    max_internal_motion: float,
    detections: int,
    static_location_ratio: float,
    flow_coherence: float,
    static_stack_overlap_ratio: float,
    person_overlap_ratio: float,
    outside_person_ratio: float,
    observations: list[dict[str, object]],
    gate_decision: str = "reject",
    gate_reason: str = "worker_body_overlap",
) -> dict[str, object]:
    return {
        "schema_version": "factory-track-receipt-v1",
        "track_id": track_id,
        "timestamps": {"first": first_timestamp, "last": last_timestamp},
        "evidence": {
            "track_id": track_id,
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "first_zone": first_zone,
            "zones_seen": zones_seen,
            "source_frames": source_frames,
            "output_frames": output_frames,
            "max_displacement": max_displacement,
            "mean_internal_motion": mean_internal_motion,
            "max_internal_motion": max_internal_motion,
            "detections": detections,
            "static_location_ratio": static_location_ratio,
            "flow_coherence": flow_coherence,
            "static_stack_overlap_ratio": static_stack_overlap_ratio,
            "person_overlap_ratio": person_overlap_ratio,
            "outside_person_ratio": outside_person_ratio,
            "observations": observations,
        },
        "diagnosis": {
            "track_id": track_id,
            "decision": "candidate" if output_frames > 0 else "uncertain",
            "reason": "source_to_output_motion" if output_frames > 0 else "source_without_output_settle",
            "flags": [],
            "evidence": {"track_id": track_id},
        },
        "perception_gate": {
            "track_id": track_id,
            "decision": gate_decision,
            "reason": gate_reason,
            "flags": ["high_person_overlap", "not_enough_object_outside_person"],
            "evidence": {
                "track_id": track_id,
                "source_frames": source_frames,
                "output_frames": output_frames,
                "zones_seen": zones_seen,
                "first_zone": first_zone,
                "max_displacement": max_displacement,
                "mean_internal_motion": mean_internal_motion,
                "max_internal_motion": max_internal_motion,
                "detections": detections,
                "person_overlap_ratio": person_overlap_ratio,
                "outside_person_ratio": outside_person_ratio,
                "static_stack_overlap_ratio": static_stack_overlap_ratio,
                "static_location_ratio": static_location_ratio,
                "flow_coherence": flow_coherence,
                "edge_like_ratio": 0.0,
            },
        },
        "review_assets": {
            "overlay_sheet_path": "",
            "overlay_video_path": "",
            "track_sheet_path": None,
            "raw_crop_paths": [],
        },
    }


def _write_person_panel_sidecar(
    path: Path,
    *,
    recommendation: str,
    max_visible_nonperson_ratio: float,
    max_estimated_visible_signal: float,
    selected_frames: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_id": path.stem.replace("-person-panel-separation", ""),
                "diagnostic_only": True,
                "recommendation": recommendation,
                "summary": {
                    "frame_count": len(selected_frames),
                    "separable_panel_candidate_frames": sum(
                        1 for frame in selected_frames if frame.get("separation_decision") == "separable_panel_candidate"
                    ),
                    "worker_body_overlap_frames": sum(
                        1 for frame in selected_frames if frame.get("separation_decision") == "worker_body_overlap"
                    ),
                    "static_or_background_edge_frames": sum(
                        1 for frame in selected_frames if frame.get("separation_decision") == "static_or_background_edge"
                    ),
                    "max_visible_nonperson_ratio": max_visible_nonperson_ratio,
                    "max_estimated_visible_signal": max_estimated_visible_signal,
                },
                "selected_frames": selected_frames,
            }
        ),
        encoding="utf-8",
    )


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


def test_select_representative_observations_keeps_short_tracks_dense() -> None:
    observations = [{"timestamp": idx} for idx in range(9)]

    assert diag.select_representative_observations(observations) == observations


def test_select_representative_observations_uses_nine_samples_for_long_tracks() -> None:
    observations = [{"timestamp": idx} for idx in range(17)]

    assert diag.select_representative_observations(observations) == [
        {"timestamp": 0},
        {"timestamp": 2},
        {"timestamp": 4},
        {"timestamp": 6},
        {"timestamp": 8},
        {"timestamp": 10},
        {"timestamp": 12},
        {"timestamp": 14},
        {"timestamp": 16},
    ]


def test_build_track_evidence_preserves_representative_observations() -> None:
    evidence = diag.build_track_evidence(
        track_points={1: [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0), (40.0, 0.0)]},
        track_motion={1: [0.1, 0.2, 0.3, 0.4, 0.5]},
        track_zones={1: ["source", "source", "source", "output", "output"]},
        track_times={1: [1.0, 2.0, 3.0, 4.0, 5.0]},
        track_detections={1: 5},
        track_person_overlaps={1: [0.0, 0.1]},
        track_observations={1: [{"timestamp": idx, "box_xywh": [idx, idx, 10, 10]} for idx in range(5)]},
    )[0]

    assert evidence.observations == [
        {"timestamp": 0, "box_xywh": [0, 0, 10, 10]},
        {"timestamp": 1, "box_xywh": [1, 1, 10, 10]},
        {"timestamp": 2, "box_xywh": [2, 2, 10, 10]},
        {"timestamp": 3, "box_xywh": [3, 3, 10, 10]},
        {"timestamp": 4, "box_xywh": [4, 4, 10, 10]},
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


def test_refresh_diagnostic_gate_receipts_merges_source_predecessor_into_output_successor(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")

    predecessor_path = receipts_dir / "track-000008.json"
    predecessor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=8,
                first_timestamp=290.632,
                last_timestamp=301.632,
                first_zone="source",
                zones_seen=["source"],
                source_frames=32,
                output_frames=0,
                max_displacement=99.017,
                mean_internal_motion=0.40993,
                max_internal_motion=0.537713,
                detections=32,
                static_location_ratio=0.25,
                flow_coherence=0.55,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.843899,
                outside_person_ratio=0.156101,
                observations=[
                    {"timestamp": 290.632, "box_xywh": [1070.929, 476.328, 140.537, 148.02], "zone": "source"},
                    {"timestamp": 296.298, "box_xywh": [1144.448, 499.951, 138.0, 110.93], "zone": "source"},
                    {"timestamp": 301.632, "box_xywh": [1146.762, 503.473, 135.928, 80.654], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        predecessor_path.with_name("track-000008-person-panel-separation.json"),
        recommendation="countable_panel_candidate",
        max_visible_nonperson_ratio=0.6085,
        max_estimated_visible_signal=0.053287,
        selected_frames=[
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
        ],
    )

    successor_path = receipts_dir / "track-000010.json"
    successor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=10,
                first_timestamp=302.965,
                last_timestamp=303.632,
                first_zone="source",
                zones_seen=["source", "output"],
                source_frames=1,
                output_frames=2,
                max_displacement=150.551,
                mean_internal_motion=0.46777,
                max_internal_motion=0.502035,
                detections=3,
                static_location_ratio=0.0,
                flow_coherence=0.71,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.932519,
                outside_person_ratio=0.067481,
                observations=[
                    {"timestamp": 302.965, "box_xywh": [806.702, 509.828, 223.104, 48.06], "zone": "source"},
                    {"timestamp": 303.298, "box_xywh": [738.027, 521.478, 225.381, 41.903], "zone": "output"},
                    {"timestamp": 303.632, "box_xywh": [658.586, 570.989, 233.761, 21.185], "zone": "output"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        successor_path.with_name("track-000010-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.0,
        max_estimated_visible_signal=0.0,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
        ],
    )

    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 290.0,
                "end_timestamp": 305.0,
                "fps": 3.0,
                "track_receipts": [str(predecessor_path), str(successor_path)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {"track_id": 8, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 8}},
                    {"track_id": 10, "decision": "candidate", "reason": "source_to_output_motion", "flags": [], "evidence": {"track_id": 10}},
                ],
                "summary": {
                    "track_count": 2,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 1},
                    "reason_counts": {"source_to_output_motion": 1, "source_without_output_settle": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    json.loads(predecessor_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(successor_path.read_text(encoding="utf-8"))["perception_gate"],
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 2,
                    "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 2},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    by_track = {row["track_id"]: row for row in result["perception_gate"]}
    assert by_track[8]["decision"] == "uncertain"
    assert by_track[8]["reason"] == "source_without_output_settle"
    assert by_track[10]["decision"] == "allow_source_token"
    assert by_track[10]["reason"] == "moving_panel_candidate"
    assert "source_token_allowed_by_person_panel_separation" in by_track[10]["flags"]
    assert by_track[10]["evidence"]["merged_predecessor_track_id"] == 8
    assert by_track[10]["evidence"]["source_frames"] == 33
    assert by_track[10]["evidence"]["output_frames"] == 2
    assert result["perception_gate_summary"]["allowed_source_token_tracks"] == [10]

    refreshed_successor = json.loads(successor_path.read_text(encoding="utf-8"))
    assert refreshed_successor["perception_gate"]["decision"] == "allow_source_token"
    assert refreshed_successor["perception_gate"]["evidence"]["merged_predecessor_track_id"] == 8


def test_refresh_diagnostic_gate_receipts_merges_source_predecessor_using_crop_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")

    predecessor_path = receipts_dir / "track-000004.json"
    predecessor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=4,
                first_timestamp=217.051,
                last_timestamp=224.717,
                first_zone="source",
                zones_seen=["source"],
                source_frames=23,
                output_frames=0,
                max_displacement=141.535,
                mean_internal_motion=0.33,
                max_internal_motion=0.44,
                detections=23,
                static_location_ratio=0.22,
                flow_coherence=0.58,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=1.0,
                outside_person_ratio=0.0,
                observations=[
                    {"timestamp": 217.051, "box_xywh": [1128.0, 492.0, 150.0, 90.0], "zone": "source"},
                    {"timestamp": 221.051, "box_xywh": [1133.0, 494.0, 149.0, 91.0], "zone": "source"},
                    {"timestamp": 224.717, "box_xywh": [1138.077, 495.782, 152.724, 91.305], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        predecessor_path.with_name("track-000004-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.0,
        max_estimated_visible_signal=0.0,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "source", "separation_decision": "worker_body_overlap"},
        ],
    )

    successor_path = receipts_dir / "track-000005.json"
    successor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=5,
                first_timestamp=225.051,
                last_timestamp=225.717,
                first_zone="source",
                zones_seen=["source", "output"],
                source_frames=1,
                output_frames=2,
                max_displacement=152.0,
                mean_internal_motion=0.42,
                max_internal_motion=0.49,
                detections=3,
                static_location_ratio=0.0,
                flow_coherence=0.62,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=1.0,
                outside_person_ratio=0.0,
                observations=[
                    {"timestamp": 225.051, "box_xywh": [1100.0, 500.0, 150.0, 90.0], "zone": "source"},
                    {"timestamp": 225.384, "box_xywh": [980.0, 514.0, 190.0, 80.0], "zone": "output"},
                    {"timestamp": 225.717, "box_xywh": [860.0, 540.0, 210.0, 60.0], "zone": "output"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        successor_path.with_name("track-000005-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.0,
        max_estimated_visible_signal=0.0,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
        ],
    )

    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 217.0,
                "end_timestamp": 226.0,
                "fps": 3.0,
                "track_receipts": [str(predecessor_path), str(successor_path)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {"track_id": 4, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 4}},
                    {"track_id": 5, "decision": "candidate", "reason": "source_to_output_motion", "flags": [], "evidence": {"track_id": 5}},
                ],
                "summary": {
                    "track_count": 2,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 1},
                    "reason_counts": {"source_to_output_motion": 1, "source_without_output_settle": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    json.loads(predecessor_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(successor_path.read_text(encoding="utf-8"))["perception_gate"],
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 2,
                    "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 2},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        diag,
        "receipt_crop_classifier_features",
        lambda payload: {
            "person_panel_crop_recommendation": "carried_panel",
            "person_panel_crop_positive_crops": 3,
            "person_panel_crop_negative_crops": 0,
            "person_panel_crop_total_crops": 3,
            "person_panel_crop_positive_ratio": 1.0,
            "person_panel_crop_max_confidence": 0.999,
        },
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    by_track = {row["track_id"]: row for row in result["perception_gate"]}
    assert by_track[5]["decision"] == "allow_source_token"
    assert "source_token_allowed_by_crop_classifier" in by_track[5]["flags"]
    assert by_track[5]["evidence"]["merged_predecessor_track_id"] == 4


def test_refresh_diagnostic_gate_receipts_merges_multi_hop_source_chain_into_output_successor(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")

    track4_path = receipts_dir / "track-000004.json"
    track4_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=4,
                first_timestamp=217.051,
                last_timestamp=224.717,
                first_zone="source",
                zones_seen=["source"],
                source_frames=23,
                output_frames=0,
                max_displacement=141.535,
                mean_internal_motion=0.33,
                max_internal_motion=0.44,
                detections=23,
                static_location_ratio=0.22,
                flow_coherence=0.58,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=1.0,
                outside_person_ratio=0.0,
                observations=[
                    {"timestamp": 217.051, "box_xywh": [1128.0, 492.0, 150.0, 90.0], "zone": "source"},
                    {"timestamp": 221.051, "box_xywh": [1133.0, 494.0, 149.0, 91.0], "zone": "source"},
                    {"timestamp": 224.717, "box_xywh": [1138.077, 495.782, 152.724, 91.305], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        track4_path.with_name("track-000004-person-panel-separation.json"),
        recommendation="countable_panel_candidate",
        max_visible_nonperson_ratio=0.520147,
        max_estimated_visible_signal=0.052764,
        selected_frames=[
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "worker_body_overlap"},
        ],
    )

    track5_path = receipts_dir / "track-000005.json"
    track5_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=5,
                first_timestamp=226.717,
                last_timestamp=231.717,
                first_zone="source",
                zones_seen=["source"],
                source_frames=15,
                output_frames=0,
                max_displacement=100.541,
                mean_internal_motion=0.36,
                max_internal_motion=0.48,
                detections=15,
                static_location_ratio=0.17,
                flow_coherence=0.62,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.684516,
                outside_person_ratio=0.315484,
                observations=[
                    {"timestamp": 226.717, "box_xywh": [1128.833, 492.359, 129.322, 189.118], "zone": "source"},
                    {"timestamp": 229.051, "box_xywh": [1134.0, 470.0, 130.0, 140.0], "zone": "source"},
                    {"timestamp": 231.717, "box_xywh": [1141.45, 445.307, 131.194, 96.0], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        track5_path.with_name("track-000005-person-panel-separation.json"),
        recommendation="countable_panel_candidate",
        max_visible_nonperson_ratio=0.680038,
        max_estimated_visible_signal=0.097314,
        selected_frames=[
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "insufficient_visibility"},
        ],
    )

    track6_path = receipts_dir / "track-000006.json"
    track6_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=6,
                first_timestamp=232.717,
                last_timestamp=233.051,
                first_zone="source",
                zones_seen=["source", "output"],
                source_frames=1,
                output_frames=1,
                max_displacement=139.186,
                mean_internal_motion=0.459188,
                max_internal_motion=0.459188,
                detections=2,
                static_location_ratio=0.0,
                flow_coherence=0.76,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.888032,
                outside_person_ratio=0.111968,
                observations=[
                    {"timestamp": 232.717, "box_xywh": [824.303, 525.408, 219.539, 46.522], "zone": "source"},
                    {"timestamp": 233.051, "box_xywh": [726.0, 548.0, 225.0, 34.0], "zone": "output"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        track6_path.with_name("track-000006-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.003905,
        max_estimated_visible_signal=0.002221,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
        ],
    )

    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 217.0,
                "end_timestamp": 234.0,
                "fps": 3.0,
                "track_receipts": [str(track4_path), str(track5_path), str(track6_path)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {"track_id": 4, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 4}},
                    {"track_id": 5, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 5}},
                    {"track_id": 6, "decision": "candidate", "reason": "source_to_output_motion", "flags": [], "evidence": {"track_id": 6}},
                ],
                "summary": {
                    "track_count": 3,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 2},
                    "reason_counts": {"source_to_output_motion": 1, "source_without_output_settle": 2},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    json.loads(track4_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(track5_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(track6_path.read_text(encoding="utf-8"))["perception_gate"],
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 3,
                    "decision_counts": {"allow_source_token": 0, "reject": 3, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 3},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    by_track = {row["track_id"]: row for row in result["perception_gate"]}
    assert by_track[6]["decision"] == "allow_source_token"
    assert by_track[6]["reason"] == "moving_panel_candidate"
    assert by_track[6]["evidence"]["merged_predecessor_track_id"] == 5
    assert by_track[6]["evidence"]["merged_predecessor_track_ids"] == [4, 5]
    assert by_track[6]["evidence"]["source_frames"] == 39
    assert by_track[6]["evidence"]["output_frames"] == 1
    assert result["perception_gate_summary"]["allowed_source_token_tracks"] == [6]


def test_refresh_diagnostic_gate_receipts_does_not_merge_distant_predecessor(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")

    predecessor_path = receipts_dir / "track-000001.json"
    predecessor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=1,
                first_timestamp=100.0,
                last_timestamp=104.0,
                first_zone="source",
                zones_seen=["source"],
                source_frames=12,
                output_frames=0,
                max_displacement=80.0,
                mean_internal_motion=0.28,
                max_internal_motion=0.41,
                detections=12,
                static_location_ratio=0.2,
                flow_coherence=0.5,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.88,
                outside_person_ratio=0.12,
                observations=[
                    {"timestamp": 100.0, "box_xywh": [900.0, 500.0, 120.0, 80.0], "zone": "source"},
                    {"timestamp": 102.0, "box_xywh": [930.0, 505.0, 120.0, 80.0], "zone": "source"},
                    {"timestamp": 104.0, "box_xywh": [960.0, 510.0, 120.0, 80.0], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        predecessor_path.with_name("track-000001-person-panel-separation.json"),
        recommendation="countable_panel_candidate",
        max_visible_nonperson_ratio=0.55,
        max_estimated_visible_signal=0.06,
        selected_frames=[
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
        ],
    )

    successor_path = receipts_dir / "track-000002.json"
    successor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=2,
                first_timestamp=111.0,
                last_timestamp=112.0,
                first_zone="source",
                zones_seen=["source", "output"],
                source_frames=1,
                output_frames=2,
                max_displacement=145.0,
                mean_internal_motion=0.31,
                max_internal_motion=0.5,
                detections=3,
                static_location_ratio=0.0,
                flow_coherence=0.6,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.95,
                outside_person_ratio=0.05,
                observations=[
                    {"timestamp": 111.0, "box_xywh": [200.0, 540.0, 210.0, 45.0], "zone": "source"},
                    {"timestamp": 111.5, "box_xywh": [150.0, 548.0, 210.0, 45.0], "zone": "output"},
                    {"timestamp": 112.0, "box_xywh": [100.0, 555.0, 210.0, 45.0], "zone": "output"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        successor_path.with_name("track-000002-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.0,
        max_estimated_visible_signal=0.0,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
        ],
    )

    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 100.0,
                "end_timestamp": 113.0,
                "fps": 3.0,
                "track_receipts": [str(predecessor_path), str(successor_path)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {"track_id": 1, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 1}},
                    {"track_id": 2, "decision": "candidate", "reason": "source_to_output_motion", "flags": [], "evidence": {"track_id": 2}},
                ],
                "summary": {
                    "track_count": 2,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 1},
                    "reason_counts": {"source_to_output_motion": 1, "source_without_output_settle": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    json.loads(predecessor_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(successor_path.read_text(encoding="utf-8"))["perception_gate"],
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 2,
                    "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 2},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    by_track = {row["track_id"]: row for row in result["perception_gate"]}
    assert by_track[2]["decision"] == "reject"
    assert by_track[2]["reason"] == "worker_body_overlap"
    assert "merged_predecessor_track_id" not in by_track[2]["evidence"]


def test_refresh_diagnostic_gate_receipts_keeps_runtime_sized_predecessor_gap_alive(tmp_path: Path) -> None:
    out_dir = tmp_path / "diagnostic"
    receipts_dir = out_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (out_dir / "overlay_video.mp4").write_bytes(b"video")

    predecessor_path = receipts_dir / "track-000001.json"
    predecessor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=1,
                first_timestamp=100.0,
                last_timestamp=104.0,
                first_zone="source",
                zones_seen=["source"],
                source_frames=12,
                output_frames=0,
                max_displacement=80.0,
                mean_internal_motion=0.28,
                max_internal_motion=0.41,
                detections=12,
                static_location_ratio=0.2,
                flow_coherence=0.5,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.88,
                outside_person_ratio=0.12,
                observations=[
                    {"timestamp": 100.0, "box_xywh": [900.0, 500.0, 120.0, 80.0], "zone": "source"},
                    {"timestamp": 102.0, "box_xywh": [930.0, 505.0, 120.0, 80.0], "zone": "source"},
                    {"timestamp": 104.0, "box_xywh": [960.0, 510.0, 120.0, 80.0], "zone": "source"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        predecessor_path.with_name("track-000001-person-panel-separation.json"),
        recommendation="countable_panel_candidate",
        max_visible_nonperson_ratio=0.55,
        max_estimated_visible_signal=0.06,
        selected_frames=[
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
        ],
    )

    successor_path = receipts_dir / "track-000002.json"
    successor_path.write_text(
        json.dumps(
            _track_receipt_payload(
                track_id=2,
                first_timestamp=107.0,
                last_timestamp=108.0,
                first_zone="source",
                zones_seen=["source", "output"],
                source_frames=1,
                output_frames=2,
                max_displacement=145.0,
                mean_internal_motion=0.31,
                max_internal_motion=0.5,
                detections=3,
                static_location_ratio=0.0,
                flow_coherence=0.6,
                static_stack_overlap_ratio=0.0,
                person_overlap_ratio=0.95,
                outside_person_ratio=0.05,
                observations=[
                    {"timestamp": 107.0, "box_xywh": [970.0, 512.0, 210.0, 45.0], "zone": "source"},
                    {"timestamp": 107.5, "box_xywh": [930.0, 520.0, 210.0, 45.0], "zone": "output"},
                    {"timestamp": 108.0, "box_xywh": [885.0, 528.0, 210.0, 45.0], "zone": "output"},
                ],
            )
        ),
        encoding="utf-8",
    )
    _write_person_panel_sidecar(
        successor_path.with_name("track-000002-person-panel-separation.json"),
        recommendation="not_panel",
        max_visible_nonperson_ratio=0.0,
        max_estimated_visible_signal=0.0,
        selected_frames=[
            {"zone": "source", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
            {"zone": "output", "separation_decision": "worker_body_overlap"},
        ],
    )

    diagnostic_path = out_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-event-diagnostic-v1",
                "video_path": "data/videos/from-pc/factory2.MOV",
                "start_timestamp": 100.0,
                "end_timestamp": 109.0,
                "fps": 5.0,
                "track_receipts": [str(predecessor_path), str(successor_path)],
                "track_receipt_cards": [],
                "overlay_sheet_path": str(out_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(out_dir / "overlay_video.mp4"),
                "diagnosis": [
                    {"track_id": 1, "decision": "uncertain", "reason": "source_without_output_settle", "flags": [], "evidence": {"track_id": 1}},
                    {"track_id": 2, "decision": "candidate", "reason": "source_to_output_motion", "flags": [], "evidence": {"track_id": 2}},
                ],
                "summary": {
                    "track_count": 2,
                    "decision_counts": {"candidate": 1, "reject": 0, "uncertain": 1},
                    "reason_counts": {"source_to_output_motion": 1, "source_without_output_settle": 1},
                    "has_source_to_output_candidate": True,
                },
                "perception_gate": [
                    json.loads(predecessor_path.read_text(encoding="utf-8"))["perception_gate"],
                    json.loads(successor_path.read_text(encoding="utf-8"))["perception_gate"],
                ],
                "perception_gate_summary": {
                    "allowed_source_token_tracks": [],
                    "track_count": 2,
                    "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 0},
                    "reason_counts": {"worker_body_overlap": 2},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diag.refresh_diagnostic_gate_receipts(diagnostic_path=diagnostic_path)

    by_track = {row["track_id"]: row for row in result["perception_gate"]}
    assert by_track[2]["decision"] == "allow_source_token"
    assert by_track[2]["evidence"]["merged_predecessor_track_id"] == 1


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
