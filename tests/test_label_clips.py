from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from app.services.training_exam_guard import sha256_file

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
    source_sha256 = manifest["samples"][0]["source_sha256"]
    firewall = tmp_path / "exam-firewall.json"
    firewall.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-exam-firewall-v2",
                "fail_closed": True,
                "intervals": [
                    {
                        "id": "neutral-path-exam",
                        "source_sha256": source_sha256,
                        "lineage_source_sha256": [source_sha256],
                        "lineage_is_transitive_complete": True,
                        "start_at": "2026-07-25T13:00:00Z",
                        "end_at": "2026-07-25T13:01:00Z",
                        "training_eligible": False,
                        "assignment_eligible": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    source_sets = tmp_path / "source-sets.json"
    source_sets.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-review-source-sets-v1",
                "fail_closed": True,
                "sets": {
                    "resolver_calibration": [],
                    "ai_evaluation_holdout": [
                        {
                            "source_sha256": source_sha256,
                            "lineage_source_sha256": [source_sha256],
                            "lineage_is_transitive_complete": True,
                            "start_at": "2026-07-25T13:00:00Z",
                            "end_at": "2026-07-25T13:01:00Z",
                        }
                    ],
                    "practice": [],
                    "qualification": [],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="refusing to label protected"):
        guard_no_exam_rows(
            manifest,
            exam_firewall_path=firewall,
            source_set_registry_path=source_sets,
        )


def test_parse_label_output_accepts_embedded_json() -> None:
    parsed = parse_label_output('text before {"decision":"refute","confidence":"high","note":"flash"}', clip_id="c1")

    assert parsed["decision"] == "refute"
    assert parsed["confidence"] == "high"
    assert majority_decision([{"decision": "assert"}, {"decision": "refute"}]) == "refute"


def make_manifest(tmp_path: Path, *, centers: list[float]) -> dict:
    stack_path = tmp_path / "stack3.npz"
    source_path = tmp_path / "neutral-source.mp4"
    source_path.write_bytes(b"neutral training source")
    np.savez_compressed(stack_path, data=np.zeros((3, 16, 16, 3), dtype=np.uint8))
    source_sha256 = sha256_file(source_path)
    return {
        "schema_version": "factory-vision-clip-dataset-v1",
        "samples": [
            {
                "candidate_id": f"candidate-{index}",
                "source": str(source_path),
                "training_eligible": True,
                "source_sha256": source_sha256,
                "lineage_source_sha256": [source_sha256],
                "lineage_is_transitive_complete": True,
                "start_at": "2026-07-25T13:00:00Z",
                "end_at": "2026-07-25T13:00:01Z",
                "center_sec": center,
                "start_sec": center - 1,
                "end_sec": center + 1,
                "paths": {"stack3": str(stack_path)},
                "label": None,
            }
            for index, center in enumerate(centers)
        ],
    }
