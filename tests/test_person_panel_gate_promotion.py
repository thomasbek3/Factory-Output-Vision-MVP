from __future__ import annotations

import json
from pathlib import Path

from app.services.person_panel_gate_promotion import promote_worker_overlap_gate_row


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def worker_overlap_row() -> dict:
    return {
        "track_id": 5,
        "decision": "reject",
        "reason": "worker_body_overlap",
        "flags": ["high_person_overlap", "not_enough_object_outside_person"],
        "evidence": {
            "track_id": 5,
            "detections": 39,
            "first_zone": "source",
            "zones_seen": ["source", "output"],
            "source_frames": 38,
            "output_frames": 1,
            "max_displacement": 603.294,
            "mean_internal_motion": 0.337425,
            "max_internal_motion": 0.730217,
            "person_overlap_ratio": 1.0,
            "outside_person_ratio": 0.0,
            "static_stack_overlap_ratio": 0.0,
            "static_location_ratio": 0.333333,
            "flow_coherence": 0.501419,
            "edge_like_ratio": 0.0,
        },
    }


def test_promote_worker_overlap_gate_row_accepts_strong_separation_receipt(tmp_path: Path) -> None:
    receipt = write_json(
        tmp_path / "diag" / "track_receipts" / "track-000005.json",
        {"review_assets": {"raw_crop_paths": []}},
    )
    write_json(
        receipt.with_name("track-000005-person-panel-separation.json"),
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
        },
    )

    promoted = promote_worker_overlap_gate_row(worker_overlap_row(), str(receipt))

    assert promoted["decision"] == "allow_source_token"
    assert promoted["reason"] == "moving_panel_candidate"
    assert "source_token_allowed_by_person_panel_separation" in promoted["flags"]


def test_promote_worker_overlap_gate_row_keeps_weak_separation_rejected(tmp_path: Path) -> None:
    receipt = write_json(
        tmp_path / "diag" / "track_receipts" / "track-000005.json",
        {"review_assets": {"raw_crop_paths": []}},
    )
    write_json(
        receipt.with_name("track-000005-person-panel-separation.json"),
        {
            "packet_id": "event0002-track000005",
            "diagnostic_only": True,
            "recommendation": "insufficient_visibility",
            "summary": {
                "frame_count": 1,
                "separable_panel_candidate_frames": 1,
                "worker_body_overlap_frames": 0,
                "static_or_background_edge_frames": 0,
                "max_visible_nonperson_ratio": 0.491658,
                "max_estimated_visible_signal": 0.048451,
            },
            "selected_frames": [
                {"zone": "source", "separation_decision": "separable_panel_candidate"},
            ],
        },
    )

    promoted = promote_worker_overlap_gate_row(worker_overlap_row(), str(receipt))

    assert promoted["decision"] == "reject"
    assert promoted["reason"] == "worker_body_overlap"
    assert "source_token_allowed_by_person_panel_separation" not in promoted["flags"]


def test_promote_worker_overlap_gate_row_uses_stronger_raw_mesh_signal_when_summary_signal_is_low(tmp_path: Path) -> None:
    receipt = write_json(
        tmp_path / "diag" / "track_receipts" / "track-000005.json",
        {"review_assets": {"raw_crop_paths": []}},
    )
    write_json(
        receipt.with_name("track-000005-person-panel-separation.json"),
        {
            "packet_id": "event0006-track000001",
            "diagnostic_only": True,
            "recommendation": "countable_panel_candidate",
            "summary": {
                "frame_count": 5,
                "separable_panel_candidate_frames": 3,
                "worker_body_overlap_frames": 1,
                "static_or_background_edge_frames": 0,
                "max_visible_nonperson_ratio": 0.822163,
                "max_estimated_visible_signal": 0.038852,
            },
            "selected_frames": [
                {
                    "zone": "source",
                    "separation_decision": "separable_panel_candidate",
                    "mesh_signal_nonperson_score": 0.055749,
                    "mesh_signal_border_score": 0.069883,
                },
                {
                    "zone": "source",
                    "separation_decision": "separable_panel_candidate",
                    "mesh_signal_nonperson_score": 0.034261,
                    "mesh_signal_border_score": 0.067007,
                },
                {
                    "zone": "source",
                    "separation_decision": "insufficient_visibility",
                    "mesh_signal_nonperson_score": 0.029959,
                    "mesh_signal_border_score": 0.020144,
                },
                {
                    "zone": "source",
                    "separation_decision": "separable_panel_candidate",
                    "mesh_signal_nonperson_score": 0.055749,
                    "mesh_signal_border_score": 0.069883,
                },
                {
                    "zone": "output",
                    "separation_decision": "worker_body_overlap",
                    "mesh_signal_nonperson_score": 0.0,
                    "mesh_signal_border_score": 0.0,
                },
            ],
        },
    )

    promoted = promote_worker_overlap_gate_row(worker_overlap_row(), str(receipt))

    assert promoted["decision"] == "allow_source_token"
    assert promoted["reason"] == "moving_panel_candidate"
