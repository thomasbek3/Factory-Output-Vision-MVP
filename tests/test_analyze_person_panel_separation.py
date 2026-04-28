import json
from pathlib import Path

import numpy as np
from PIL import Image

from scripts import analyze_person_panel_separation as separation
from scripts.analyze_person_panel_separation import (
    analyze_frame_person_panel_separation,
    build_person_panel_separation_report,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(path)


def _mesh_fill(image: np.ndarray, *, left: int, top: int, width: int, height: int) -> None:
    image[top : top + height, left : left + width] = (220, 220, 220)
    image[top : top + height : 6, left : left + width] = (20, 20, 20)
    image[top : top + height, left : left + width : 6] = (20, 20, 20)


def _person_mask(height: int, width: int, *, left: int, top: int, right: int, bottom: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


def test_protruding_panel_outside_person_silhouette_is_separable_candidate():
    image = np.full((140, 160, 3), 235, dtype=np.uint8)
    person_mask = _person_mask(140, 160, left=42, top=18, right=92, bottom=126)
    image[person_mask] = (90, 85, 80)
    _mesh_fill(image, left=76, top=46, width=42, height=58)

    result = analyze_frame_person_panel_separation(
        image,
        panel_box_xywh=(76, 46, 42, 58),
        person_box_xywh=(28, 12, 98, 118),
        person_mask=person_mask,
        frame_path="frame_000060.jpg",
        timestamp=97.667,
        zone="source",
    )

    assert result["bbox_outside_person_ratio"] == 0.0
    assert result["visible_nonperson_ratio"] > 0.45
    assert result["mesh_signal_nonperson_score"] > 0.08
    assert result["separation_decision"] == "separable_panel_candidate"


def test_body_only_region_inside_person_silhouette_stays_worker_overlap():
    image = np.full((140, 160, 3), 225, dtype=np.uint8)
    person_mask = _person_mask(140, 160, left=36, top=16, right=112, bottom=128)
    image[person_mask] = (92, 88, 84)
    image[52:100, 58:94] = (70, 68, 66)

    result = analyze_frame_person_panel_separation(
        image,
        panel_box_xywh=(58, 52, 36, 48),
        person_box_xywh=(32, 12, 88, 120),
        person_mask=person_mask,
        frame_path="frame_000081.jpg",
        timestamp=104.667,
        zone="source",
    )

    assert result["visible_nonperson_ratio"] < 0.02
    assert result["mesh_signal_nonperson_score"] < 0.02
    assert result["separation_decision"] == "worker_body_overlap"


def test_static_background_mesh_away_from_person_is_rejected():
    image = np.full((140, 200, 3), 235, dtype=np.uint8)
    person_mask = _person_mask(140, 200, left=24, top=18, right=86, bottom=126)
    image[person_mask] = (88, 82, 80)
    _mesh_fill(image, left=132, top=34, width=42, height=72)

    result = analyze_frame_person_panel_separation(
        image,
        panel_box_xywh=(132, 34, 42, 72),
        person_box_xywh=(20, 14, 74, 118),
        person_mask=person_mask,
        frame_path="frame_000100.jpg",
        timestamp=111.0,
        zone="output",
    )

    assert result["person_bbox_overlap_ratio"] == 0.0
    assert result["silhouette_border_contact_ratio"] == 0.0
    assert result["separation_decision"] == "static_or_background_edge"


def test_select_observations_keeps_short_tracks_dense():
    observations = [{"timestamp": float(index)} for index in range(9)]

    selected = separation._select_observations(observations)

    assert selected == observations


def test_select_observations_uses_nine_samples_for_long_tracks():
    observations = [{"timestamp": float(index)} for index in range(17)]

    selected = separation._select_observations(observations)

    assert selected == [
        {"timestamp": 0.0},
        {"timestamp": 2.0},
        {"timestamp": 4.0},
        {"timestamp": 6.0},
        {"timestamp": 8.0},
        {"timestamp": 10.0},
        {"timestamp": 12.0},
        {"timestamp": 14.0},
        {"timestamp": 16.0},
    ]


def test_build_report_reads_transfer_packets_and_writes_summary_artifacts(tmp_path: Path):
    frame_a = tmp_path / "frames" / "frame_000060.jpg"
    frame_b = tmp_path / "frames" / "frame_000081.jpg"
    frame_c = tmp_path / "frames" / "frame_000100.jpg"
    for frame_path in (frame_a, frame_b, frame_c):
        image = np.full((140, 160, 3), 235, dtype=np.uint8)
        person_mask = _person_mask(140, 160, left=42, top=18, right=92, bottom=126)
        image[person_mask] = (90, 85, 80)
        _mesh_fill(image, left=76, top=46, width=42, height=58)
        _write_image(frame_path, image)

    receipt_path = tmp_path / "data" / "diagnostics" / "event-windows" / "factory2-event0002-test" / "track_receipts" / "track-000005.json"
    packet_json_path = receipt_path.with_name("track-000005-transfer-packet.json")
    report_path = tmp_path / "data" / "reports" / "factory2_transfer_review_packets.json"
    output_path = tmp_path / "data" / "reports" / "factory2_person_panel_separation.json"

    _write_json(
        receipt_path,
        {
            "track_id": 5,
            "evidence": {
                "source_frames": 38,
                "output_frames": 1,
                "person_overlap_ratio": 1.0,
                "outside_person_ratio": 0.0,
                "observations": [
                    {
                        "timestamp": 97.667,
                        "frame_path": str(frame_a),
                        "box_xywh": [76, 46, 42, 58],
                        "zone": "source",
                        "person_overlap": 0.75,
                    },
                    {
                        "timestamp": 104.667,
                        "frame_path": str(frame_b),
                        "box_xywh": [76, 46, 42, 58],
                        "zone": "source",
                        "person_overlap": 0.80,
                    },
                    {
                        "timestamp": 111.0,
                        "frame_path": str(frame_c),
                        "box_xywh": [76, 46, 42, 58],
                        "zone": "output",
                        "person_overlap": 0.82,
                    },
                ],
            },
            "review_assets": {
                "track_sheet_path": str(receipt_path.with_name("track-000005-sheet.jpg")),
                "raw_crop_paths": [],
            },
            "perception_gate": {"decision": "reject", "reason": "worker_body_overlap"},
        },
    )
    _write_json(
        report_path,
        {
            "schema_version": "factory-transfer-review-packets-v1",
            "packet_count": 1,
            "packets": [
                {
                    "track_id": 5,
                    "window": {"start_timestamp": 78.0, "end_timestamp": 118.0, "fps": 3.0, "frame_count": 120},
                    "decision": "reject",
                    "reason": "worker_body_overlap",
                    "failure_link": "worker_body_overlap",
                    "ranking_features": {"person_overlap_ratio": 1.0, "outside_person_ratio": 0.0},
                    "assets": {
                        "receipt_json_path": str(receipt_path.relative_to(tmp_path)),
                        "transfer_packet_json_path": str(packet_json_path.relative_to(tmp_path)),
                    },
                }
            ],
        },
    )

    report = build_person_panel_separation_report(
        packets_report=report_path,
        output=output_path,
        repo_root=tmp_path,
        limit=1,
        force=True,
        person_box_detector=lambda frame_path: [(28.0, 12.0, 98.0, 118.0)],
        silhouette_estimator=lambda image, person_box, panel_box: _person_mask(image.shape[0], image.shape[1], left=42, top=18, right=92, bottom=126),
    )

    assert report["diagnostic_only"] is True
    assert report["packet_count"] == 1
    packet = report["packets"][0]
    assert packet["packet_id"] == "event0002-track000005"
    assert packet["event"] == "event0002"
    assert packet["track_id"] == 5
    assert packet["recommendation"] == "countable_panel_candidate"
    assert len(packet["selected_frames"]) == 3
    assert packet["reason_strings"]
    assert output_path.exists()
    assert (tmp_path / packet["packet_diagnostic_path"]).exists()
