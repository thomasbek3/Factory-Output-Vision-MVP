from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.teacher_provider import (
    DryRunTeacherProvider,
    FakeTeacherProvider,
    build_teacher_labels_from_windows,
    provider_for_name,
)
from scripts import generate_onboarding_teacher_labels


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_window_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-onboarding-window-manifest-v1",
                "station_id": "line-a",
                "segment_manifest_path": "/tmp/segments.json",
                "window_sec": 1.0,
                "candidate_types": ["positive_candidate", "idle_candidate", "hard_negative_candidate"],
                "windows": [
                    {
                        "station_id": "line-a",
                        "window_id": "win-positive",
                        "segment_id": "segment",
                        "segment_path": "/tmp/segment.mkv",
                        "clip_path": "/tmp/win-positive.mp4",
                        "candidate_type": "positive_candidate",
                        "start_offset_sec": 1.0,
                        "duration_sec": 1.0,
                        "label_status": "unreviewed",
                        "evidence_role": "candidate_only_not_truth",
                        "generated_by": "fixed_offset_segment_sampler_v1",
                    },
                    {
                        "station_id": "line-a",
                        "window_id": "win-idle",
                        "segment_id": "segment",
                        "segment_path": "/tmp/segment.mkv",
                        "clip_path": "/tmp/win-idle.mp4",
                        "candidate_type": "idle_candidate",
                        "start_offset_sec": 0.0,
                        "duration_sec": 1.0,
                        "label_status": "unreviewed",
                        "evidence_role": "candidate_only_not_truth",
                        "generated_by": "fixed_offset_segment_sampler_v1",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_dry_run_teacher_provider_outputs_bronze_pending_no_network(tmp_path: Path) -> None:
    window_manifest = tmp_path / "window_manifest.json"
    _write_window_manifest(window_manifest)

    payload = build_teacher_labels_from_windows(
        window_manifest_path=window_manifest,
        provider=DryRunTeacherProvider(),
    )

    schema = json.loads((REPO_ROOT / "validation/schemas/teacher_label.schema.json").read_text())
    for key in schema["required"]:
        assert key in payload
    assert payload["case_id"] == "onboarding:line-a"
    assert payload["station_id"] == "line-a"
    assert payload["provider"]["network_calls_made"] is False
    assert payload["refuses_validation_truth"] is True
    assert len(payload["labels"]) == 2
    for label in payload["labels"]:
        assert label["teacher_output_status"] == "unclear"
        assert label["label_authority_tier"] == "bronze"
        assert label["review_status"] == "pending"
        assert label["validation_truth_eligible"] is False
        assert label["training_eligible"] is False


def test_fake_teacher_provider_can_emit_statuses_but_still_refuses_truth(tmp_path: Path) -> None:
    window_manifest = tmp_path / "window_manifest.json"
    _write_window_manifest(window_manifest)

    payload = build_teacher_labels_from_windows(
        window_manifest_path=window_manifest,
        provider=FakeTeacherProvider(statuses_by_window_id={"win-positive": "countable"}),
    )

    labels = {row["window_id"]: row for row in payload["labels"]}
    assert labels["win-positive"]["teacher_output_status"] == "countable"
    assert labels["win-positive"]["confidence_tier"] == "high"
    assert labels["win-positive"]["label_authority_tier"] == "bronze"
    assert labels["win-positive"]["validation_truth_eligible"] is False
    assert labels["win-positive"]["training_eligible"] is False
    assert payload["provider"]["network_calls_made"] is False


def test_cloud_teacher_provider_is_disabled_by_default() -> None:
    with pytest.raises(ValueError, match="disabled by default"):
        provider_for_name("openai")


def test_generate_onboarding_teacher_labels_cli_dry_run(tmp_path: Path, capsys) -> None:
    window_manifest = tmp_path / "window_manifest.json"
    output = tmp_path / "teacher_labels.json"
    _write_window_manifest(window_manifest)

    exit_code = generate_onboarding_teacher_labels.main(
        ["--window-manifest", str(window_manifest), "--output", str(output), "--force"]
    )

    captured = capsys.readouterr()
    payload = json.loads(output.read_text())
    assert exit_code == 0
    assert '"label_count": 2' in captured.out
    assert payload["provider"]["name"] == "dry_run_fixture"
    assert payload["provider"]["network_calls_made"] is False


def test_generate_onboarding_teacher_labels_cli_refuses_cloud_by_default(tmp_path: Path, capsys) -> None:
    window_manifest = tmp_path / "window_manifest.json"
    output = tmp_path / "teacher_labels.json"
    _write_window_manifest(window_manifest)

    exit_code = generate_onboarding_teacher_labels.main(
        ["--window-manifest", str(window_manifest), "--provider", "openai", "--output", str(output)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "cloud teacher providers are disabled by default" in captured.err
    assert output.exists() is False
