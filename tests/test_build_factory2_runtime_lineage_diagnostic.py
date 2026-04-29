from __future__ import annotations

import json
from pathlib import Path

from scripts.build_factory2_runtime_lineage_diagnostic import build_runtime_lineage_diagnostic_from_capture
from scripts.build_morning_proof_report import summarize_diagnostic


def _write_placeholder(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_runtime_lineage_diagnostic_from_capture_writes_runtime_backed_accepted_receipt(tmp_path: Path) -> None:
    overlay_frame = tmp_path / "frames" / "frame_000001.jpg"
    _write_placeholder(overlay_frame, "not-a-real-image")
    capture_payload = {
        "schema_version": "factory2-runtime-lineage-capture-v1",
        "video_path": "data/videos/from-pc/factory2.MOV",
        "calibration_path": "data/calibration/factory2_runtime_calibration.json",
        "model_path": "models/panel_in_transit.pt",
        "person_model_path": "yolo11n.pt",
        "start_timestamp": 299.0,
        "end_timestamp": 308.0,
        "fps": 10.0,
        "frame_count": 3,
        "overlay_frames": [str(overlay_frame)],
        "events": [
            {
                "event_id": "factory2-runtime-only-0007",
                "event_ts": 305.708,
                "track_id": 7,
                "count_total": 22,
                "reason": "approved_delivery_chain",
                "gate_decision": {
                    "decision": "allow_source_token",
                    "reason": "moving_panel_candidate",
                    "flags": ["source_token_allowed_by_crop_classifier"],
                },
                "source_track_id": 3,
                "source_token_id": "source-token-42",
                "chain_id": "proof-source-track:3",
                "provenance_status": "inherited_live_source_token",
                "predecessor_chain_track_ids": [3],
            }
        ],
        "track_histories": {
            "3": [
                {
                    "timestamp": 303.1,
                    "box_xywh": [803.0, 513.0, 208.0, 39.0],
                    "confidence": 0.49,
                    "zone": "source",
                    "motion": 0.39,
                    "person_overlap": 0.18,
                    "outside_person_ratio": 0.82,
                    "static_stack_overlap_ratio": 0.0,
                    "frame_path": str(overlay_frame),
                },
                {
                    "timestamp": 303.3,
                    "box_xywh": [757.0, 514.0, 232.0, 43.0],
                    "confidence": 0.27,
                    "zone": "source",
                    "motion": 0.44,
                    "person_overlap": 0.21,
                    "outside_person_ratio": 0.79,
                    "static_stack_overlap_ratio": 0.0,
                    "frame_path": str(overlay_frame),
                },
            ],
            "7": [
                {
                    "timestamp": 305.5,
                    "box_xywh": [699.0, 541.0, 247.0, 31.0],
                    "confidence": 0.31,
                    "zone": "output",
                    "motion": 0.42,
                    "person_overlap": 0.24,
                    "outside_person_ratio": 0.76,
                    "static_stack_overlap_ratio": 0.0,
                    "frame_path": str(overlay_frame),
                }
            ],
        },
    }

    out_dir = tmp_path / "runtime-proof"
    payload = build_runtime_lineage_diagnostic_from_capture(
        capture_payload=capture_payload,
        event_id="factory2-runtime-only-0007",
        out_dir=out_dir,
        force=True,
        media_maker=lambda **kwargs: (
            Path(kwargs["sheet_path"]).write_text("sheet", encoding="utf-8"),
            Path(kwargs["video_path"]).write_text("video", encoding="utf-8"),
        ),
        receipt_card_maker=lambda **kwargs: None,
    )

    diagnostic_path = out_dir / "diagnostic.json"
    assert diagnostic_path.exists()
    assert payload["perception_gate_summary"]["allowed_source_token_tracks"] == [7]

    diagnostic = summarize_diagnostic(diagnostic_path)
    assert diagnostic["accepted_count"] == 1
    accepted = next(item for item in diagnostic["track_decision_receipts"] if item["decision"] == "allow_source_token")
    assert accepted["track_id"] == 7
    assert accepted["source_token_key"] == "runtime-source-token:source-token-42"

    receipt_path = out_dir / "track_receipts" / "track-000007.json"
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    evidence = receipt_payload["perception_gate"]["evidence"]
    assert evidence["runtime_source_token_id"] == "source-token-42"
    assert evidence["merged_predecessor_track_ids"] == [3]


def test_build_runtime_lineage_diagnostic_from_capture_rejects_synthetic_output_fallback_token(tmp_path: Path) -> None:
    overlay_frame = tmp_path / "frames" / "frame_000001.jpg"
    _write_placeholder(overlay_frame, "not-a-real-image")
    capture_payload = {
        "schema_version": "factory2-runtime-lineage-capture-v1",
        "video_path": "data/videos/from-pc/factory2.MOV",
        "video_fps": 29.97,
        "start_timestamp": 300.0,
        "end_timestamp": 307.0,
        "fps": 10.0,
        "frame_count": 1,
        "overlay_frames": [str(overlay_frame)],
        "events": [
            {
                "event_id": "factory2-runtime-only-0007",
                "event_ts": 305.708,
                "track_id": 108,
                "count_total": 16,
                "reason": "approved_delivery_chain",
                "gate_decision": {
                    "decision": "allow_source_token",
                    "reason": "moving_panel_candidate",
                    "flags": ["source_token_allowed_by_crop_classifier"],
                },
                "source_track_id": 105,
                "source_token_id": "source-token-65",
                "chain_id": "proof-source-track:105",
                "provenance_status": "synthetic_approved_chain_token",
            }
        ],
        "track_histories": {
            "108": [
                {
                    "timestamp": 305.708,
                    "box_xywh": [659.0, 580.0, 247.0, 42.0],
                    "confidence": 1.0,
                    "zone": "output",
                    "motion": 0.0,
                    "person_overlap": 0.87,
                    "outside_person_ratio": 0.13,
                    "static_stack_overlap_ratio": 0.0,
                    "frame_path": str(overlay_frame),
                }
            ]
        },
    }

    out_dir = tmp_path / "runtime-proof-synthetic"
    payload = build_runtime_lineage_diagnostic_from_capture(
        capture_payload=capture_payload,
        event_id="factory2-runtime-only-0007",
        out_dir=out_dir,
        force=True,
        media_maker=lambda **kwargs: (
            Path(kwargs["sheet_path"]).write_text("sheet", encoding="utf-8"),
            Path(kwargs["video_path"]).write_text("video", encoding="utf-8"),
        ),
        receipt_card_maker=lambda **kwargs: None,
    )

    assert payload["perception_gate_summary"]["allowed_source_token_tracks"] == []
    diagnostic = summarize_diagnostic(out_dir / "diagnostic.json")
    assert diagnostic["accepted_count"] == 0
    suppressed = diagnostic["track_decision_receipts"][0]
    assert suppressed["failure_link"] == "incomplete_source_to_output_path"
    assert suppressed["reason"] == "synthetic_runtime_fallback_token"
