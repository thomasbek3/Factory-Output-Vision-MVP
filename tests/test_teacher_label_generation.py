from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.teacher_generate_labels import DryRunFixtureProvider, build_teacher_labels


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_teacher_generate_labels_dry_run_outputs_only_bronze_pending(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-event-evidence-v1",
                "case_id": "fixture_case",
                "privacy_mode": "offline_local",
                "video": {"path": "video.mov", "sha256": "abc"},
                "source_artifacts": {"observed_events_path": "observed.json"},
                "model_settings": {},
                "windows": [
                    {
                        "window_id": "fixture-count-0001",
                        "window_type": "count_event",
                        "time_window": {"start_sec": 1.0, "center_sec": 2.0, "end_sec": 3.0},
                        "frame_window": {
                            "start_frame_index": 10,
                            "center_frame_index": 20,
                            "end_frame_index": 30,
                        },
                        "confidence_tier": "unknown",
                        "duplicate_risk": "unknown",
                        "miss_risk": "unknown",
                        "label_authority_tier": "bronze",
                    }
                ],
                "review_window_metadata": [],
            }
        ),
        encoding="utf-8",
    )

    payload = build_teacher_labels(evidence_path=evidence_path, provider=DryRunFixtureProvider())

    schema = _read_json(REPO_ROOT / "validation/schemas/teacher_label.schema.json")
    for key in schema["required"]:
        assert key in payload
    assert payload["provider"]["network_calls_made"] is False
    assert payload["refuses_validation_truth"] is True
    assert len(payload["labels"]) == 1
    label = payload["labels"][0]
    assert label["teacher_output_status"] == "unclear"
    assert label["label_authority_tier"] == "bronze"
    assert label["review_status"] == "pending"
    assert label["validation_truth_eligible"] is False
    assert label["training_eligible"] is False
