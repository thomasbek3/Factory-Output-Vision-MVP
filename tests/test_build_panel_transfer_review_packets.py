import json
from pathlib import Path

import pytest

from scripts.build_panel_transfer_review_packets import build_transfer_review_packets


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _track(track_id, source_frames, output_frames, displacement, flow, *, outside=0.0, static=0.0, decision="reject"):
    return {
        "track_id": track_id,
        "decision": decision,
        "reason": "worker_body_overlap",
        "failure_link": "worker_body_overlap",
        "worker_overlap_detail": "fully_entangled_with_worker",
        "flags": ["high_person_overlap"],
        "evidence_summary": {
            "source_frames": source_frames,
            "output_frames": output_frames,
            "max_displacement": displacement,
            "flow_coherence": flow,
            "person_overlap_ratio": 1.0 - outside,
            "outside_person_ratio": outside,
            "static_stack_overlap_ratio": static,
        },
        "receipt_json_path": f"diag/track_receipts/track-{track_id:06d}.json",
        "receipt_card_path": f"diag/track_receipts/track-{track_id:06d}-sheet.jpg",
        "raw_crop_paths": [f"diag/track_receipts/track-{track_id:06d}-crops/crop-01-source.jpg"],
    }


def test_ranks_temporal_source_output_tracks_above_single_frame_protrusion(tmp_path):
    diagnostic_path = tmp_path / "diag" / "diagnostic.json"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "packets.json"

    diagnostic = {
        "diagnostic_path": "diag/diagnostic.json",
        "window": {"start_timestamp": 78.0, "end_timestamp": 118.0, "fps": 3.0},
        "overlay_sheet_path": "diag/overlay_sheet.jpg",
        "overlay_video_path": "diag/overlay_video.mp4",
        "track_decision_receipts": [
            _track(7, 1, 0, 0.0, 0.0, outside=0.29, decision="uncertain"),
            _track(5, 38, 1, 603.294, 0.501419, outside=0.0),
            _track(2, 34, 0, 273.665, 0.134594, outside=0.0),
        ],
    }
    _write_json(diagnostic_path, diagnostic)
    _write_json(report_path, {"schema_version": "factory2-morning-proof-report-v1", "diagnostics": [{"diagnostic_path": "diag/diagnostic.json"}]})

    result = build_transfer_review_packets(report_path, output_path, repo_root=tmp_path, force=True, limit=3)

    assert [p["track_id"] for p in result["packets"]][:3] == [5, 2, 7]
    assert result["packets"][0]["ranking_features"]["source_output_presence"] is True
    assert result["packets"][2]["ranking_features"]["single_frame_penalty"] is True
    assert output_path.exists()


def test_packet_schema_contains_review_fields_and_assets(tmp_path):
    diagnostic_path = tmp_path / "diag" / "diagnostic.json"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "packets.json"
    receipt_card = tmp_path / "diag" / "track_receipts" / "track-000005-sheet.jpg"
    crop = tmp_path / "diag" / "track_receipts" / "track-000005-crops" / "crop-01-source.jpg"
    receipt_card.parent.mkdir(parents=True, exist_ok=True)
    receipt_card.write_bytes(b"fake-jpeg-card")
    crop.parent.mkdir(parents=True, exist_ok=True)
    crop.write_bytes(b"fake-jpeg-crop")

    diagnostic = {
        "diagnostic_path": "diag/diagnostic.json",
        "window": {"start_timestamp": 78.0, "end_timestamp": 118.0, "fps": 3.0},
        "overlay_sheet_path": "diag/overlay_sheet.jpg",
        "overlay_video_path": "diag/overlay_video.mp4",
        "track_decision_receipts": [_track(5, 38, 1, 603.294, 0.501419)],
    }
    _write_json(diagnostic_path, diagnostic)
    _write_json(report_path, {"diagnostics": [{"diagnostic_path": "diag/diagnostic.json"}]})

    result = build_transfer_review_packets(report_path, output_path, repo_root=tmp_path, force=True, limit=1)
    packet = result["packets"][0]

    assert packet["schema_version"] == "factory-transfer-review-packet-v1"
    assert packet["review_label_template"] == {
        "reviewer": "",
        "discrete_panel_visible": None,
        "separable_from_worker": None,
        "source_origin_supported": None,
        "output_entry_supported": None,
        "should_mint_source_token": None,
        "should_increment_count": None,
        "evidence_frame_indices": [],
        "notes": "",
    }
    assert packet["review_question"].startswith("Does this temporal packet prove")
    assert packet["assets"]["receipt_card_path"].endswith("track-000005-sheet.jpg")
    assert packet["assets"]["transfer_packet_json_path"].endswith("track-000005-transfer-packet.json")
    assert packet["assets"]["transfer_packet_image_path"].endswith("track-000005-transfer-packet.jpg")
    assert (tmp_path / packet["assets"]["transfer_packet_json_path"]).exists()
    assert (tmp_path / packet["assets"]["transfer_packet_image_path"]).read_bytes() == b"fake-jpeg-card"


def test_refuses_to_overwrite_without_force(tmp_path):
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "packets.json"
    _write_json(report_path, {"diagnostics": []})
    output_path.write_text("existing")

    with pytest.raises(FileExistsError):
        build_transfer_review_packets(report_path, output_path, repo_root=tmp_path, force=False)
