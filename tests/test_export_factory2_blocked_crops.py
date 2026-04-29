from __future__ import annotations

import json
from pathlib import Path

from scripts import export_factory2_blocked_crops as exporter


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_crop(path: Path, payload: bytes = b"crop") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_export_blocked_crops_writes_worker_overlap_dataset_items(tmp_path: Path) -> None:
    crop_a = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000001-crops" / "crop-01-source.jpg", b"a")
    crop_b = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000001-crops" / "crop-02-output.jpg", b"b")
    card = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000001-sheet.jpg", b"card")
    visual_a = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000001-person-panel-separation-frame_000001.png", b"va")
    visual_b = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000001-person-panel-separation-frame_000002.png", b"vb")

    receipt = _write_json(
        tmp_path / "diag" / "track_receipts" / "track-000001.json",
        {
            "track_id": 1,
            "timestamps": {"first": 97.667, "last": 111.0},
            "evidence": {
                "observations": [
                    {"timestamp": 97.667, "zone": "source", "frame_path": "diag/frames/frame_000001.jpg"},
                    {"timestamp": 101.0, "zone": "output", "frame_path": "diag/frames/frame_000002.jpg"},
                ]
            },
            "review_assets": {
                "track_sheet_path": str(card),
                "raw_crop_paths": [str(crop_a), str(crop_b)],
            },
        },
    )
    sidecar = _write_json(
        tmp_path / "diag" / "track_receipts" / "track-000001-person-panel-separation.json",
        {
            "track_id": 1,
            "recommendation": "countable_panel_candidate",
            "selected_frames": [
                {
                    "timestamp": 97.667,
                    "zone": "source",
                    "separation_decision": "separable_panel_candidate",
                    "visual_receipt_path": str(visual_a),
                },
                {
                    "timestamp": 101.0,
                    "zone": "output",
                    "separation_decision": "worker_body_overlap",
                    "visual_receipt_path": str(visual_b),
                },
            ],
            "summary": {
                "frame_count": 2,
                "max_visible_nonperson_ratio": 0.58,
                "max_estimated_visible_signal": 0.04,
            },
        },
    )
    proof_report = _write_json(
        tmp_path / "proof.json",
        {
            "decision_receipt_index": {
                "accepted": [],
                "suppressed": [
                    {
                        "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                        "window": {"start_timestamp": 78.0, "end_timestamp": 118.0, "fps": 3.0},
                        "track_id": 1,
                        "decision": "reject",
                        "reason": "worker_body_overlap",
                        "failure_link": "worker_body_overlap",
                        "worker_overlap_detail": "fully_entangled_with_worker",
                        "evidence_summary": {
                            "person_overlap_ratio": 1.0,
                            "outside_person_ratio": 0.0,
                            "source_frames": 38,
                            "output_frames": 1,
                        },
                        "receipt_json_path": str(receipt),
                        "receipt_card_path": str(card),
                        "raw_crop_paths": [str(crop_a), str(crop_b)],
                        "receipt_timestamps": {"first": 97.667, "last": 111.0},
                        "person_panel_separation_path": str(sidecar),
                        "person_panel_recommendation": "countable_panel_candidate",
                        "person_panel_summary": {"frame_count": 2},
                    }
                ],
                "uncertain": [],
                "counts": {"accepted": 0, "suppressed": 1, "uncertain": 0},
            }
        },
    )
    output_report = tmp_path / "out" / "blocked_crop_dataset.json"
    dataset_dir = tmp_path / "out" / "dataset"

    result = exporter.export_blocked_crops(
        proof_report_path=proof_report,
        output_report_path=output_report,
        dataset_dir=dataset_dir,
        force=False,
    )

    assert result["schema_version"] == "factory-blocked-crop-dataset-v1"
    assert result["blocked_track_count"] == 1
    assert result["blocked_crop_count"] == 2
    assert result["positive_crop_count"] == 0
    assert result["items"][0]["dataset_bucket"] == "blocked_worker_overlap"
    assert result["items"][0]["track_id"] == 1
    assert result["items"][0]["timestamp_seconds"] == 97.667
    assert result["items"][0]["zone"] == "source"
    assert result["items"][0]["gate_decision"] == "reject"
    assert result["items"][0]["gate_reason"] == "worker_body_overlap"
    assert result["items"][0]["person_panel_recommendation"] == "countable_panel_candidate"
    assert result["items"][0]["label_placeholder"] == {
        "crop_label": "unclear",
        "mask_status": "missing",
        "notes": "",
    }
    assert Path(result["items"][0]["exported_crop_path"]).exists()
    assert Path(result["items"][0]["exported_crop_path"]).read_bytes() == b"a"
    assert result["items"][1]["timestamp_seconds"] == 101.0
    assert result["items"][1]["zone"] == "output"
    assert result["items"][1]["visual_receipt_path"] == str(visual_b)
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_export_blocked_crops_includes_accepted_receipts_as_positive_boundary_examples(tmp_path: Path) -> None:
    crop = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000005-crops" / "crop-01-source.jpg", b"pos")
    card = _write_crop(tmp_path / "diag" / "track_receipts" / "track-000005-sheet.jpg", b"card")
    receipt = _write_json(
        tmp_path / "diag" / "track_receipts" / "track-000005.json",
        {
            "track_id": 5,
            "timestamps": {"first": 144.5, "last": 147.3},
            "evidence": {
                "observations": [
                    {"timestamp": 144.5, "zone": "source", "frame_path": "diag/frames/frame_000050.jpg"}
                ]
            },
            "review_assets": {
                "track_sheet_path": str(card),
                "raw_crop_paths": [str(crop)],
            },
        },
    )
    sidecar = _write_json(
        tmp_path / "diag" / "track_receipts" / "track-000005-person-panel-separation.json",
        {
            "track_id": 5,
            "recommendation": "countable_panel_candidate",
            "selected_frames": [
                {
                    "timestamp": 144.5,
                    "zone": "source",
                    "separation_decision": "separable_panel_candidate",
                }
            ],
        },
    )
    proof_report = _write_json(
        tmp_path / "proof.json",
        {
            "decision_receipt_index": {
                "accepted": [
                    {
                        "accepted_cluster_id": "accepted-cluster-001",
                        "counts_toward_accepted_total": True,
                        "diagnostic_path": str(tmp_path / "diag" / "diagnostic.json"),
                        "window": {"start_timestamp": 145.0, "end_timestamp": 185.0, "fps": 5.0},
                        "track_id": 5,
                        "decision": "allow_source_token",
                        "reason": "moving_panel_candidate",
                        "failure_link": "source_token_approved",
                        "worker_overlap_detail": "fully_entangled_with_worker",
                        "evidence_summary": {
                            "person_overlap_ratio": 1.0,
                            "outside_person_ratio": 0.0,
                            "source_frames": 9,
                            "output_frames": 2,
                        },
                        "receipt_json_path": str(receipt),
                        "receipt_card_path": str(card),
                        "raw_crop_paths": [str(crop)],
                        "receipt_timestamps": {"first": 144.5, "last": 147.3},
                        "person_panel_separation_path": str(sidecar),
                        "person_panel_recommendation": "countable_panel_candidate",
                        "person_panel_summary": {"frame_count": 1},
                    }
                ],
                "suppressed": [],
                "uncertain": [],
                "counts": {"accepted": 1, "suppressed": 0, "uncertain": 0},
            }
        },
    )

    result = exporter.export_blocked_crops(
        proof_report_path=proof_report,
        output_report_path=tmp_path / "out" / "dataset.json",
        dataset_dir=tmp_path / "out" / "dataset",
        force=False,
    )

    assert result["blocked_crop_count"] == 0
    assert result["positive_crop_count"] == 1
    assert result["items"][0]["dataset_bucket"] == "accepted_positive_boundary"
    assert result["items"][0]["gate_decision"] == "allow_source_token"
    assert result["items"][0]["label_placeholder"]["crop_label"] == "carried_panel"
    assert Path(result["items"][0]["exported_crop_path"]).read_bytes() == b"pos"
