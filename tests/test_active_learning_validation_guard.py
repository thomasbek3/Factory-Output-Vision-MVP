from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_video import run_validation
from scripts.validation_truth_guard import ValidationTruthError


def test_validate_video_rejects_teacher_labels_as_truth(tmp_path: Path) -> None:
    teacher_truth = tmp_path / "teacher_labels.json"
    teacher_truth.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "case_id": "poisoned_case",
                "source_evidence_path": "evidence.json",
                "privacy_mode": "offline_local",
                "provider": {
                    "name": "dry_run_fixture",
                    "mode": "local_fixture",
                    "network_calls_made": False,
                },
                "refuses_validation_truth": True,
                "labels": [],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-video-manifest-v1",
                "case_id": "poisoned_case",
                "status": "candidate",
                "promotion_status": "not_promoted",
                "video": {
                    "path": "demo/fixture.mov",
                    "sha256": "abc",
                    "duration_sec": 10.0,
                    "width": 1920,
                    "height": 1080,
                    "codec": "hevc",
                },
                "truth": {
                    "rule_id": "bad",
                    "expected_total": 1,
                    "count_rule": "bad",
                    "truth_ledger_path": teacher_truth.as_posix(),
                },
                "runtime": {
                    "demo_count_mode": "live_reader_snapshot",
                    "counting_mode": "event_based",
                    "playback_speed": 1.0,
                    "processing_fps": 10.0,
                    "reader_fps": 10.0,
                    "runtime_calibration_path": None,
                    "model_path": None,
                },
                "proof_artifacts": {
                    "observed_events": "observed.json",
                    "comparison_report": "comparison.json",
                    "validation_report": "validation.json",
                },
                "proof_summary": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationTruthError, match="teacher/VLM artifacts cannot be validation truth"):
        run_validation(
            manifest_path=manifest_path,
            backend_port=None,
            frontend_port=None,
            dry_run=False,
            execute=False,
            use_existing_artifacts=False,
            auto_start=False,
            skip_preview=False,
            skip_launch=False,
            skip_capture=False,
            skip_compare=False,
            output_path=None,
            force=False,
        )
