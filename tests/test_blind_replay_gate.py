from __future__ import annotations

import json
from pathlib import Path

from app.services.blind_replay_gate import SCHEMA_VERSION, run_blind_replay_gate


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-video-manifest-v1",
                "case_id": "heldout_case",
                "status": "candidate",
                "video": {"path": "/tmp/video.mov", "duration_sec": 10, "sha256": "abc"},
                "truth": {"expected_total": 2, "truth_ledger_path": "/tmp/truth.json"},
                "runtime": {"playback_speed": 1.0},
                "proof_artifacts": {},
            }
        ),
        encoding="utf-8",
    )


def test_blind_replay_gate_passes_only_clean_runtime_validation(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "gate.json"
    _write_manifest(manifest)

    def fake_validation_runner(**kwargs):
        assert kwargs["execute"] is True
        assert kwargs["dry_run"] is False
        assert kwargs["use_existing_artifacts"] is False
        return {
            "mode": "execute",
            "validation_report": "/tmp/validation_report.json",
            "report": {
                "truth": {"expected_total": 2},
                "proof_summary": {
                    "observed_event_count": 2,
                    "matched_count": 2,
                    "missing_truth_count": 0,
                    "unexpected_observed_count": 0,
                    "first_divergence": None,
                },
            },
        }

    payload = run_blind_replay_gate(
        manifest_path=manifest,
        output_path=output,
        execute=True,
        force=True,
        validation_runner=fake_validation_runner,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["passed"] is True
    assert payload["status"] == "passed"
    assert payload["count_authority"] == "existing_yolo_event_runtime_only"
    assert payload["teacher_labels_used_as_truth"] is False
    assert payload["fail_reasons"] == []
    assert "matched_expected_total" in payload["pass_reasons"]
    assert json.loads(output.read_text())["passed"] is True


def test_blind_replay_gate_fails_on_runtime_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "gate.json"
    _write_manifest(manifest)

    def fake_validation_runner(**kwargs):
        return {
            "mode": "execute",
            "validation_report": "/tmp/validation_report.json",
            "report": {
                "truth": {"expected_total": 2},
                "proof_summary": {
                    "observed_event_count": 1,
                    "matched_count": 1,
                    "missing_truth_count": 1,
                    "unexpected_observed_count": 0,
                    "first_divergence": {"type": "missing_truth"},
                },
            },
        }

    payload = run_blind_replay_gate(
        manifest_path=manifest,
        output_path=output,
        execute=True,
        force=True,
        validation_runner=fake_validation_runner,
    )

    assert payload["passed"] is False
    assert payload["status"] == "failed"
    assert "matched_count_does_not_equal_expected_total" in payload["fail_reasons"]
    assert "missing_truth_events" in payload["fail_reasons"]
    assert "first_divergence_present" in payload["fail_reasons"]


def test_blind_replay_gate_dry_run_never_passes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "gate.json"
    _write_manifest(manifest)

    def fake_validation_runner(**kwargs):
        assert kwargs["execute"] is False
        assert kwargs["dry_run"] is True
        return {"mode": "dry-run", "commands": {"launch": ["python", "scripts/start_factory2_demo_stack.py"]}}

    payload = run_blind_replay_gate(
        manifest_path=manifest,
        output_path=output,
        execute=False,
        force=True,
        validation_runner=fake_validation_runner,
    )

    assert payload["passed"] is False
    assert payload["status"] == "failed"
    assert "dry_run_does_not_pass_gate" in payload["fail_reasons"]
    assert "validation_runtime_not_executed" in payload["fail_reasons"]
