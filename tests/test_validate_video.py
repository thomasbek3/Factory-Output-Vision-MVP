from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_video import (
    build_capture_command,
    build_compare_command,
    build_launch_command,
    build_validation_report,
    calculate_pacing,
    resolve_manifest_path,
    run_validation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest(name: str) -> dict:
    return json.loads((REPO_ROOT / "validation/test_cases" / name).read_text(encoding="utf-8"))


def test_resolve_manifest_path_from_registry() -> None:
    manifest_path = resolve_manifest_path(
        case_id="img3254_clean22_candidate",
        manifest_path=None,
        registry_path=REPO_ROOT / "validation/registry.json",
    )

    assert manifest_path == Path("validation/test_cases/img3254_clean22.json")


def test_build_launch_command_uses_manifest_runtime_settings() -> None:
    manifest = _manifest("img3254_clean22.json")

    command = build_launch_command(manifest, backend_port=8192, frontend_port=5274)

    assert command[1] == "scripts/start_factory2_demo_stack.py"
    assert command[command.index("--backend-port") + 1] == "8192"
    assert command[command.index("--frontend-port") + 1] == "5274"
    assert command[command.index("--video") + 1] == "demo/IMG_3254.MOV"
    assert command[command.index("--model") + 1] == "models/img3254_active_panel_v4_yolov8n.pt"
    assert command[command.index("--event-track-max-age") + 1] == "52"
    assert command[command.index("--event-track-min-frames") + 1] == "12"
    assert command[command.index("--event-detection-cluster-distance") + 1] == "250"
    assert "--no-runtime-calibration" in command


def test_build_capture_and_compare_commands() -> None:
    manifest = _manifest("img3262.json")

    capture = build_capture_command(
        manifest,
        output_path=Path("data/reports/observed.json"),
        backend_port=8099,
        auto_start=True,
    )
    compare = build_compare_command(
        manifest,
        observed_events_path=Path("data/reports/observed.json"),
        output_path=Path("data/reports/comparison.json"),
    )

    assert capture[capture.index("--base-url") + 1] == "http://127.0.0.1:8099"
    assert capture[capture.index("--output") + 1] == "data/reports/observed.json"
    assert "--auto-start" in capture
    assert compare[compare.index("--truth-ledger") + 1] == "data/reports/img3262_human_truth_ledger.v2.json"
    assert compare[compare.index("--observed-events") + 1] == "data/reports/observed.json"


def test_calculate_pacing_from_observed_events() -> None:
    pacing = calculate_pacing(
        {
            "events": [
                {"event_ts": 10.0, "reader_frame_time": 100.0},
                {"event_ts": 20.0, "reader_frame_time": 110.5},
            ]
        }
    )

    assert pacing is not None
    assert pacing["source_delta_sec"] == 10.0
    assert pacing["wall_delta_sec"] == 10.5
    assert pacing["wall_per_source"] == 1.05


def test_build_validation_report_merges_comparison_and_pacing() -> None:
    manifest = _manifest("img3254_clean22.json")

    report = build_validation_report(
        manifest=manifest,
        observed_payload={
            "events": [
                {"event_ts": 1.0, "reader_frame_time": 10.0},
                {"event_ts": 11.0, "reader_frame_time": 20.0},
            ]
        },
        comparison_payload={
            "observed_event_count": 22,
            "matched_count": 22,
            "missing_truth_count": 0,
            "unexpected_observed_count": 0,
            "first_divergence": None,
        },
        commands={"launch": ["cmd"]},
    )

    assert report["schema_version"] == "factory-vision-validation-report-v1"
    assert report["case_id"] == "img3254_clean22_candidate"
    assert report["proof_summary"]["matched_count"] == 22
    assert report["proof_summary"]["wall_per_source"] == 1.0


def test_run_validation_defaults_to_dry_run_without_execute() -> None:
    result = run_validation(
        manifest_path=REPO_ROOT / "validation/test_cases/img3262.json",
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

    assert result["mode"] == "dry-run"
    assert "commands" in result
    assert result["outputs"]["validation_report"].endswith("_validation_report.validation_run.json")


def test_run_validation_can_write_report_from_existing_artifacts(tmp_path: Path) -> None:
    output_path = tmp_path / "report.json"

    result = run_validation(
        manifest_path=REPO_ROOT / "validation/test_cases/img3254_clean22.json",
        backend_port=None,
        frontend_port=None,
        dry_run=False,
        execute=True,
        use_existing_artifacts=True,
        auto_start=False,
        skip_preview=False,
        skip_launch=False,
        skip_capture=False,
        skip_compare=False,
        output_path=output_path,
        force=False,
    )

    assert result["mode"] == "execute"
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["case_id"] == "img3254_clean22_candidate"
    assert report["proof_summary"]["matched_count"] == 22
    assert report["proof_summary"]["missing_truth_count"] == 0
