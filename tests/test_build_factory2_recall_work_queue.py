from __future__ import annotations

import json
from pathlib import Path

from scripts import build_factory2_recall_work_queue as queue


def test_load_reviewed_accepts_filters_factory2_accepts(tmp_path: Path) -> None:
    manifest_path = tmp_path / "reviewed.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "accepted": [
                    {
                        "decision": "ACCEPT",
                        "label_id": "a",
                        "label": {
                            "frame_id": "factory2_t000097.85",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "data/videos/selected_frames/autopilot-v1/factory2_t000097.85.jpg",
                                "timestamp_seconds": 97.849,
                            },
                            "confidence": 0.74,
                        },
                    },
                    {
                        "decision": "ACCEPT",
                        "label_id": "b",
                        "label": {
                            "frame_id": "real_factory_t001364.74",
                            "metadata": {
                                "video_path": "data/videos/from-pc/real_factory.MOV",
                                "frame_path": "data/videos/selected_frames/autopilot-v1/real_factory_t001364.74.jpg",
                                "timestamp_seconds": 1364.745,
                            },
                            "confidence": 0.21,
                        },
                    },
                ],
                "uncertain": [
                    {
                        "decision": "UNCERTAIN",
                        "label_id": "c",
                        "label": {
                            "frame_id": "factory2_t000222.38",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "data/videos/selected_frames/autopilot-v1/factory2_t000222.38.jpg",
                                "timestamp_seconds": 222.384,
                            },
                            "confidence": 0.54,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = queue.load_reviewed_accepts(manifest_path, video_path="data/videos/from-pc/factory2.MOV")

    assert rows == [
        queue.ReviewedAccept(
            label_id="a",
            frame_id="factory2_t000097.85",
            frame_path="data/videos/selected_frames/autopilot-v1/factory2_t000097.85.jpg",
            video_path="data/videos/from-pc/factory2.MOV",
            timestamp_seconds=97.849,
            confidence=0.74,
        )
    ]


def test_cluster_reviewed_accepts_merges_nearby_timestamps() -> None:
    accepts = [
        queue.ReviewedAccept("a", "factory2_t000097.85", "f1.jpg", "data/videos/from-pc/factory2.MOV", 97.849, 0.74),
        queue.ReviewedAccept("b", "factory2_t000222.38", "f2.jpg", "data/videos/from-pc/factory2.MOV", 222.384, 0.54),
        queue.ReviewedAccept("c", "factory2_t000257.96", "f3.jpg", "data/videos/from-pc/factory2.MOV", 257.965, 0.68),
        queue.ReviewedAccept("d", "factory2_t000275.76", "f4.jpg", "data/videos/from-pc/factory2.MOV", 275.756, 0.71),
        queue.ReviewedAccept("e", "factory2_t000293.55", "f5.jpg", "data/videos/from-pc/factory2.MOV", 293.546, 0.57),
        queue.ReviewedAccept("f", "factory2_t000311.34", "f6.jpg", "data/videos/from-pc/factory2.MOV", 311.337, 0.52),
        queue.ReviewedAccept("g", "factory2_t000364.71", "f7.jpg", "data/videos/from-pc/factory2.MOV", 364.709, 0.83),
        queue.ReviewedAccept("h", "factory2_t000418.08", "f8.jpg", "data/videos/from-pc/factory2.MOV", 418.081, 0.51),
    ]

    clusters = queue.cluster_reviewed_accepts(accepts, cluster_gap_seconds=25.0)

    assert [cluster.frame_ids for cluster in clusters] == [
        ["factory2_t000097.85"],
        ["factory2_t000222.38"],
        [
            "factory2_t000257.96",
            "factory2_t000275.76",
            "factory2_t000293.55",
            "factory2_t000311.34",
        ],
        ["factory2_t000364.71"],
        ["factory2_t000418.08"],
    ]
    assert clusters[2].first_timestamp == 257.965
    assert clusters[2].last_timestamp == 311.337
    assert clusters[2].peak_confidence == 0.71


def test_build_work_queue_marks_existing_proof_coverage(tmp_path: Path) -> None:
    reviewed_manifest = tmp_path / "reviewed.json"
    reviewed_manifest.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "accepted": [
                    {
                        "decision": "ACCEPT",
                        "label_id": "a",
                        "label": {
                            "frame_id": "factory2_t000097.85",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "f1.jpg",
                                "timestamp_seconds": 97.849,
                            },
                            "confidence": 0.74,
                        },
                    },
                    {
                        "decision": "ACCEPT",
                        "label_id": "b",
                        "label": {
                            "frame_id": "factory2_t000257.96",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "f2.jpg",
                                "timestamp_seconds": 257.965,
                            },
                            "confidence": 0.68,
                        },
                    },
                    {
                        "decision": "ACCEPT",
                        "label_id": "c",
                        "label": {
                            "frame_id": "factory2_t000275.76",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "f3.jpg",
                                "timestamp_seconds": 275.756,
                            },
                            "confidence": 0.71,
                        },
                    },
                    {
                        "decision": "ACCEPT",
                        "label_id": "d",
                        "label": {
                            "frame_id": "factory2_t000364.71",
                            "metadata": {
                                "video_path": "data/videos/from-pc/factory2.MOV",
                                "frame_path": "f4.jpg",
                                "timestamp_seconds": 364.709,
                            },
                            "confidence": 0.83,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    proof_report = tmp_path / "proof.json"
    proof_report.write_text(
        json.dumps(
            {
                "diagnostics": [
                    {
                        "diagnostic_path": "data/diagnostics/event-windows/factory2-event0002/diagnostic.json",
                        "window": {"start_timestamp": 78.0, "end_timestamp": 118.0},
                    },
                    {
                        "diagnostic_path": "data/diagnostics/event-windows/factory2-event0006/diagnostic.json",
                        "window": {"start_timestamp": 350.0, "end_timestamp": 390.0},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "queue.json"

    result = queue.build_work_queue(
        reviewed_manifest_path=reviewed_manifest,
        proof_report_path=proof_report,
        output_path=output_path,
        video_path="data/videos/from-pc/factory2.MOV",
        cluster_gap_seconds=25.0,
        window_padding_seconds=20.0,
        force=False,
    )

    assert result["schema_version"] == "factory2-recall-work-queue-v1"
    assert result["accepted_frame_count"] == 4
    assert result["cluster_count"] == 3
    assert result["covered_cluster_count"] == 2
    assert result["uncovered_cluster_count"] == 1
    assert result["clusters"][0]["covered_by_existing_diagnostic"] is True
    assert result["clusters"][0]["covering_diagnostic_paths"] == [
        "data/diagnostics/event-windows/factory2-event0002/diagnostic.json"
    ]
    assert result["clusters"][1]["frame_ids"] == [
        "factory2_t000257.96",
        "factory2_t000275.76",
    ]
    assert result["clusters"][1]["covered_by_existing_diagnostic"] is False
    assert result["clusters"][1]["suggested_start_timestamp"] == 237.965
    assert result["clusters"][1]["suggested_end_timestamp"] == 295.756
    assert result["clusters"][2]["covered_by_existing_diagnostic"] is True
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
