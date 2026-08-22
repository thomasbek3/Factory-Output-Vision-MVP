from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.clip_dataset import extract_clip_dataset
from scripts.label_clips import guard_no_exam_rows
from app.services.exam_gate import DEFAULT_EXAM_CLIP_OFFSETS_SEC


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAM_GOLD_PATH = REPO_ROOT / "validation" / "exam" / "exam_gold_positives.json"


def test_tracked_exam_gold_is_durable_and_inert() -> None:
    payload = json.loads(EXAM_GOLD_PATH.read_text(encoding="utf-8"))

    assert payload["schema"] == "exam_gold_positives_v1"
    assert payload["training_eligible"] is False
    assert payload["role"] == "exam_answer_key_never_train"
    assert len(payload["events"]) == 7
    assert [row["place_wall_clock"] for row in payload["events"]] == [
        "15:24:15",
        "15:30:30",
        "15:34:52",
        "15:40:23",
        "15:46:24",
        "15:52:12",
        "15:58:01",
    ]


def test_exam_clip_offsets_stay_pinned_to_gold_key() -> None:
    assert DEFAULT_EXAM_CLIP_OFFSETS_SEC == [165.0, 510.0, 781.0, 1104.0, 1475.0, 1822.0, 2172.0]


def test_label_guard_rejects_rows_derived_from_tracked_exam_gold() -> None:
    payload = json.loads(EXAM_GOLD_PATH.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "factory-vision-clip-dataset-v1",
        "samples": [
            {
                "candidate_id": row["id"],
                "source": row["segment_file"],
                "center_sec": row["offset_in_segment_sec"],
                "training_eligible": payload["training_eligible"],
            }
            for row in payload["events"]
        ],
    }

    with pytest.raises(ValueError, match="training-ineligible"):
        guard_no_exam_rows(manifest)


def test_training_manifest_extraction_rejects_training_ineligible_rows(tmp_path: Path) -> None:
    payload = json.loads(EXAM_GOLD_PATH.read_text(encoding="utf-8"))
    event = payload["events"][0]
    candidate = {
        "candidate_id": event["id"],
        "source": event["segment_file"],
        "center_sec": event["offset_in_segment_sec"],
        "start_sec": event["offset_in_segment_sec"] - 8.0,
        "end_sec": event["offset_in_segment_sec"] + 8.0,
        "training_eligible": False,
    }

    with pytest.raises(ValueError, match="training-ineligible"):
        extract_clip_dataset(
            candidates=[candidate],
            output_dir=tmp_path,
            output_zone_polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        )
