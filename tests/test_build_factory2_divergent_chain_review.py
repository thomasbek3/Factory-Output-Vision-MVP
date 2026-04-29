from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts import build_factory2_divergent_chain_review as chain_review


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_test_video(path: Path, *, fps: float, frame_count: int, size: tuple[int, int] = (320, 240)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for index in range(frame_count):
        frame = np.full((size[1], size[0], 3), (index * 5) % 255, dtype=np.uint8)
        cv2.putText(frame, f"f{index:03d}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()
    return path


def test_build_divergent_chain_review_writes_review_manifest_csv_and_images(tmp_path: Path) -> None:
    video_path = _write_test_video(tmp_path / "video.mp4", fps=10.0, frame_count=80)
    runtime_audit = _write_json(
        tmp_path / "runtime_audit.json",
        {
            "schema_version": "factory2-runtime-event-audit-v1",
            "video_path": str(video_path),
            "video_fps": 10.0,
            "events": [
                {
                    "event_ts": 3.2,
                    "track_id": 7,
                    "count_total": 12,
                    "reason": "approved_delivery_chain",
                    "provenance_status": "inherited_live_source_token",
                    "source_track_id": 7,
                },
                {
                    "event_ts": 5.0,
                    "track_id": 8,
                    "count_total": 13,
                    "reason": "approved_delivery_chain",
                    "provenance_status": "synthetic_approved_chain_token",
                    "source_track_id": 5,
                },
            ],
            "track_histories": {
                "5": [
                    {
                        "timestamp": 1.0,
                        "box_xywh": [220.0, 60.0, 60.0, 80.0],
                        "confidence": 1.0,
                        "zone": "source",
                        "person_overlap": 0.7,
                        "outside_person_ratio": 0.3,
                        "static_stack_overlap_ratio": 0.0,
                    },
                    {
                        "timestamp": 1.2,
                        "box_xywh": [225.0, 62.0, 58.0, 78.0],
                        "confidence": 1.0,
                        "zone": "source",
                        "person_overlap": 0.68,
                        "outside_person_ratio": 0.32,
                        "static_stack_overlap_ratio": 0.0,
                    },
                ],
                "6": [
                    {
                        "timestamp": 2.2,
                        "box_xywh": [230.0, 64.0, 54.0, 76.0],
                        "confidence": 1.0,
                        "zone": "source",
                        "person_overlap": 0.52,
                        "outside_person_ratio": 0.48,
                        "static_stack_overlap_ratio": 0.0,
                    }
                ],
                "7": [
                    {
                        "timestamp": 3.0,
                        "box_xywh": [210.0, 70.0, 60.0, 60.0],
                        "confidence": 1.0,
                        "zone": "source",
                        "person_overlap": 0.2,
                        "outside_person_ratio": 0.8,
                        "static_stack_overlap_ratio": 0.0,
                    },
                    {
                        "timestamp": 3.2,
                        "box_xywh": [120.0, 140.0, 90.0, 32.0],
                        "confidence": 1.0,
                        "zone": "output",
                        "person_overlap": 0.85,
                        "outside_person_ratio": 0.15,
                        "static_stack_overlap_ratio": 0.0,
                    },
                ],
                "8": [
                    {
                        "timestamp": 5.0,
                        "box_xywh": [118.0, 142.0, 92.0, 30.0],
                        "confidence": 1.0,
                        "zone": "output",
                        "person_overlap": 0.9,
                        "outside_person_ratio": 0.1,
                        "static_stack_overlap_ratio": 0.0,
                    }
                ],
                "9": [
                    {
                        "timestamp": 5.7,
                        "box_xywh": [122.0, 144.0, 94.0, 28.0],
                        "confidence": 1.0,
                        "zone": "output",
                        "person_overlap": 0.82,
                        "outside_person_ratio": 0.18,
                        "static_stack_overlap_ratio": 0.4,
                    }
                ],
            },
        },
    )
    lineage_report = _write_json(
        tmp_path / "lineage_report.json",
        {
            "schema_version": "factory2-synthetic-lineage-report-v1",
            "synthetic_events": [
                {
                    "event_ts": 5.0,
                    "track_id": 8,
                    "source_track_id": 5,
                    "count_total": 13,
                    "provenance_status": "synthetic_approved_chain_token",
                    "recommended_search_start_seconds": 0.8,
                    "recommended_search_end_seconds": 6.0,
                    "is_divergent": True,
                    "source_gap_seconds": 3.8,
                }
            ],
        },
    )
    divergence_report = _write_json(
        tmp_path / "divergence_report.json",
        {
            "schema_version": "factory2-proof-runtime-divergence-v1",
            "divergent_events": [
                {
                    "event_id": "factory2-runtime-only-0007",
                    "event_ts": 5.0,
                    "status": "shared_source_lineage_no_distinct_proof_receipt",
                }
            ],
        },
    )
    output_report = tmp_path / "out" / "divergent_chain_review.json"
    package_dir = tmp_path / "out" / "package"

    result = chain_review.build_divergent_chain_review(
        runtime_audit_path=runtime_audit,
        lineage_report_path=lineage_report,
        divergence_report_path=divergence_report,
        output_report_path=output_report,
        package_dir=package_dir,
        force=False,
    )

    assert result["schema_version"] == "factory2-divergent-chain-review-v1"
    assert result["event_count"] == 1
    assert result["item_count"] >= 5
    event = result["events"][0]
    assert event["event_id"] == "factory2-runtime-only-0007"
    assert event["runtime_track_id"] == 8
    assert event["source_track_id"] == 5
    assert event["prior_runtime_event"]["track_id"] == 7
    track_classes = {item["track_id"]: item["track_class"] for item in event["track_summaries"]}
    assert track_classes[5] == "source_only"
    assert track_classes[7] == "source_to_output"
    assert track_classes[8] == "output_only"
    assert any(item["track_role"] == "divergent_runtime_event" for item in result["items"])
    assert any(item["track_role"] == "prior_runtime_event" for item in result["items"])
    first_item = result["items"][0]
    assert Path(first_item["frame_image_path"]).exists()
    assert Path(first_item["crop_image_path"]).exists()
    assert first_item["label_placeholder"]["crop_label"] == "unclear"
    assert first_item["label_placeholder"]["relation_label"] == "unclear"
    assert json.loads(output_report.read_text(encoding="utf-8")) == result

    csv_rows = list(csv.DictReader((package_dir / "review_labels.csv").read_text(encoding="utf-8").splitlines()))
    assert len(csv_rows) == result["item_count"]
    assert csv_rows[0]["crop_label"] == "unclear"
    assert csv_rows[0]["relation_label"] == "unclear"
    assert (package_dir / "README.md").exists()
    assert (package_dir / "review_manifest.json").exists()


def test_build_divergent_chain_review_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    video_path = _write_test_video(tmp_path / "video.mp4", fps=10.0, frame_count=20)
    runtime_audit = _write_json(
        tmp_path / "runtime_audit.json",
        {
            "schema_version": "factory2-runtime-event-audit-v1",
            "video_path": str(video_path),
            "video_fps": 10.0,
            "events": [
                {
                    "event_ts": 5.0,
                    "track_id": 8,
                    "count_total": 13,
                    "reason": "approved_delivery_chain",
                    "provenance_status": "synthetic_approved_chain_token",
                    "source_track_id": 5,
                }
            ],
            "track_histories": {
                "5": [
                    {
                        "timestamp": 1.0,
                        "box_xywh": [220.0, 60.0, 60.0, 80.0],
                        "confidence": 1.0,
                        "zone": "source",
                        "person_overlap": 0.7,
                        "outside_person_ratio": 0.3,
                        "static_stack_overlap_ratio": 0.0,
                    }
                ],
                "8": [
                    {
                        "timestamp": 5.0,
                        "box_xywh": [118.0, 142.0, 92.0, 30.0],
                        "confidence": 1.0,
                        "zone": "output",
                        "person_overlap": 0.9,
                        "outside_person_ratio": 0.1,
                        "static_stack_overlap_ratio": 0.0,
                    }
                ],
            },
        },
    )
    lineage_report = _write_json(
        tmp_path / "lineage_report.json",
        {
            "schema_version": "factory2-synthetic-lineage-report-v1",
            "synthetic_events": [
                {
                    "event_ts": 5.0,
                    "track_id": 8,
                    "source_track_id": 5,
                    "recommended_search_start_seconds": 0.8,
                    "recommended_search_end_seconds": 6.0,
                    "is_divergent": True,
                }
            ],
        },
    )
    divergence_report = _write_json(
        tmp_path / "divergence_report.json",
        {
            "schema_version": "factory2-proof-runtime-divergence-v1",
            "divergent_events": [{"event_id": "factory2-runtime-only-0007", "event_ts": 5.0}],
        },
    )
    output_report = tmp_path / "out" / "divergent_chain_review.json"
    package_dir = tmp_path / "out" / "package"

    chain_review.build_divergent_chain_review(
        runtime_audit_path=runtime_audit,
        lineage_report_path=lineage_report,
        divergence_report_path=divergence_report,
        output_report_path=output_report,
        package_dir=package_dir,
        force=False,
    )

    with pytest.raises(FileExistsError):
        chain_review.build_divergent_chain_review(
            runtime_audit_path=runtime_audit,
            lineage_report_path=lineage_report,
            divergence_report_path=divergence_report,
            output_report_path=output_report,
            package_dir=package_dir,
            force=False,
        )
