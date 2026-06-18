from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.label_clips import (
    guard_no_exam_rows,
    label_manifest_with_codex,
    label_manifest_with_human_times,
    majority_decision,
    parse_label_output,
)


def test_codex_labeler_parses_json_and_uses_three_vote_majority(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path, centers=[10.0])
    outputs = iter(
        [
            '{"decision":"assert","confidence":"high","note":"carry place leave"}',
            '{"decision":"refute","confidence":"medium","note":"walk-by"}',
            '{"decision":"assert","confidence":"high","note":"placed"}',
        ]
    )

    def fake_runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=next(outputs), stderr="")

    labeled = label_manifest_with_codex(manifest, votes=3, work_dir=tmp_path, runner=fake_runner)

    assert labeled["samples"][0]["label"] == "assert"
    assert len(labeled["samples"][0]["label_votes"]) == 3


def test_human_timestamp_ingest_maps_nearest_candidates(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path, centers=[10.0, 31.0, 80.0])

    labeled = label_manifest_with_human_times(manifest, times_sec=[29.0], match_tolerance_sec=5.0)

    assert [row["label"] for row in labeled["samples"]] == ["refute", "assert", "refute"]


def test_exam_window_never_labeled(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path, centers=[10.0])
    manifest["samples"][0]["source"] = "/tmp/pipeline_day2_full/exam_clip.mp4"

    with pytest.raises(ValueError, match="refusing to label exam"):
        guard_no_exam_rows(manifest)


def test_parse_label_output_accepts_embedded_json() -> None:
    parsed = parse_label_output('text before {"decision":"refute","confidence":"high","note":"flash"}', clip_id="c1")

    assert parsed["decision"] == "refute"
    assert parsed["confidence"] == "high"
    assert majority_decision([{"decision": "assert"}, {"decision": "refute"}]) == "refute"


def make_manifest(tmp_path: Path, *, centers: list[float]) -> dict:
    stack_path = tmp_path / "stack3.npz"
    np.savez_compressed(stack_path, data=np.zeros((3, 16, 16, 3), dtype=np.uint8))
    return {
        "schema_version": "factory-vision-clip-dataset-v1",
        "samples": [
            {
                "candidate_id": f"candidate-{index}",
                "source": "/tmp/train.mp4",
                "center_sec": center,
                "start_sec": center - 1,
                "end_sec": center + 1,
                "paths": {"stack3": str(stack_path)},
                "label": None,
            }
            for index, center in enumerate(centers)
        ],
    }
