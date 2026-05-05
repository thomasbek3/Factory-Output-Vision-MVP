from __future__ import annotations

from pathlib import Path

from scripts.build_real_factory_diagnostic_action_dataset import (
    dedupe_negative_candidates,
    load_learning_negative_timestamps,
    scale_box_xyxy,
    timestamp_is_far_from_anchors,
    yolo_line_from_xyxy,
)


def test_yolo_line_clips_and_normalizes_box() -> None:
    assert yolo_line_from_xyxy([-10, 20, 110, 80], width=100, height=100) == "0 0.500000 0.500000 1.000000 0.600000"


def test_scale_box_uses_reference_dimensions() -> None:
    assert scale_box_xyxy([960, 540, 1920, 1080], width=960, height=540) == [480, 270, 960, 540]


def test_timestamp_filter_excludes_anchor_neighborhood() -> None:
    anchors = [448.0, 1026.0]

    assert timestamp_is_far_from_anchors(410.0, anchors) is True
    assert timestamp_is_far_from_anchors(430.0, anchors) is False
    assert timestamp_is_far_from_anchors(1055.0, anchors) is True


def test_learning_negatives_skip_candidates_near_draft_anchors(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text(
        """
        {
          "false_positive_candidates": [
            {"candidate_id": "near-anchor", "event_ts": 421.0},
            {"candidate_id": "far-fp", "event_ts": 808.0}
          ],
          "motion_window_candidates": [
            {"candidate_id": "far-motion", "center_timestamp": 1200.0},
            {"candidate_id": "near-motion", "center_timestamp": 1404.0}
          ]
        }
        """,
        encoding="utf-8",
    )

    negatives = load_learning_negative_timestamps(packet, anchors=[448.0, 1404.0])

    assert [item["source_id"] for item in negatives] == ["far-fp", "far-motion"]


def test_dedupe_negative_candidates_keeps_sorted_gap() -> None:
    negatives = dedupe_negative_candidates(
        [
            {"timestamp_seconds": 20.0, "source_id": "b", "reason": "fixture"},
            {"timestamp_seconds": 10.0, "source_id": "a", "reason": "fixture"},
            {"timestamp_seconds": 12.0, "source_id": "skip", "reason": "fixture"},
            {"timestamp_seconds": 28.0, "source_id": "c", "reason": "fixture"},
        ],
        min_gap_sec=6.0,
    )

    assert [item["source_id"] for item in negatives] == ["a", "b", "c"]
