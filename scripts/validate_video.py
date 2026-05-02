#!/usr/bin/env python3
"""Orchestrate the manifest-backed real app validation workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = "factory-vision-validation-report-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _python_executable() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def resolve_manifest_path(*, case_id: str | None, manifest_path: Path | None, registry_path: Path) -> Path:
    if manifest_path is not None:
        return manifest_path
    if not case_id:
        raise ValueError("either --case-id or --manifest is required")
    registry = _read_json(registry_path)
    for entry in registry.get("cases") or []:
        if entry.get("case_id") == case_id:
            return Path(entry["manifest_path"])
    raise KeyError(f"case_id not found in {registry_path}: {case_id}")


def build_preview_command(manifest: dict[str, Any], *, force: bool) -> list[str]:
    video_path = manifest["video"]["path"]
    out_dir = Path("data/videos/preview_sheets") / manifest["case_id"]
    command = [
        _python_executable(),
        "scripts/preview_video_frames.py",
        video_path,
        "--out-dir",
        out_dir.as_posix(),
    ]
    if force:
        command.append("--force")
    return command


def build_launch_command(
    manifest: dict[str, Any],
    *,
    backend_port: int | None = None,
    frontend_port: int | None = None,
) -> list[str]:
    runtime = manifest["runtime"]
    video = manifest["video"]
    launch = manifest.get("launch") or {}
    command = [
        _python_executable(),
        "scripts/start_factory2_demo_stack.py",
        "--backend-port",
        str(backend_port or launch.get("backend_port") or 8092),
        "--frontend-port",
        str(frontend_port or launch.get("frontend_port") or 5174),
        "--video",
        video["path"],
        "--playback-speed",
        f"{float(runtime['playback_speed']):g}",
        "--processing-fps",
        f"{float(runtime['processing_fps']):g}",
        "--reader-fps",
        f"{float(runtime['reader_fps']):g}",
    ]
    if runtime.get("runtime_calibration_path"):
        command.extend(["--calibration", runtime["runtime_calibration_path"]])
    else:
        command.append("--no-runtime-calibration")
    if runtime.get("model_path"):
        command.extend(["--model", runtime["model_path"]])
    if runtime.get("yolo_confidence") is not None:
        command.extend(["--yolo-confidence", f"{float(runtime['yolo_confidence']):g}"])
    if runtime.get("event_track_max_age") is not None:
        command.extend(["--event-track-max-age", str(int(runtime["event_track_max_age"]))])
    if runtime.get("event_track_min_frames") is not None:
        command.extend(["--event-track-min-frames", str(int(runtime["event_track_min_frames"]))])
    if runtime.get("event_detection_cluster_distance") is not None:
        command.extend(
            [
                "--event-detection-cluster-distance",
                f"{float(runtime['event_detection_cluster_distance']):g}",
            ]
        )
    return command


def default_output_paths(manifest: dict[str, Any]) -> dict[str, Path]:
    case_id = manifest["case_id"]
    return {
        "observed_events": Path("data/reports") / f"{case_id}_app_observed_events.validation_run.json",
        "comparison_report": Path("data/reports") / f"{case_id}_app_vs_truth.validation_run.json",
        "validation_report": Path("data/reports") / f"{case_id}_validation_report.validation_run.json",
    }


def build_capture_command(
    manifest: dict[str, Any],
    *,
    output_path: Path,
    backend_port: int | None = None,
    auto_start: bool = False,
) -> list[str]:
    launch = manifest.get("launch") or {}
    port = backend_port or launch.get("backend_port") or 8092
    max_wait_sec = float(manifest["video"]["duration_sec"]) + 180.0
    command = [
        _python_executable(),
        "scripts/capture_factory2_app_run_events.py",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--output",
        output_path.as_posix(),
        "--poll-interval-sec",
        "5",
        "--max-wait-sec",
        f"{max_wait_sec:g}",
        "--force",
    ]
    if auto_start:
        command.append("--auto-start")
    return command


def build_compare_command(
    manifest: dict[str, Any],
    *,
    observed_events_path: Path,
    output_path: Path,
) -> list[str]:
    return [
        _python_executable(),
        "scripts/compare_factory2_app_run_to_truth_ledger.py",
        "--truth-ledger",
        manifest["truth"]["truth_ledger_path"],
        "--observed-events",
        observed_events_path.as_posix(),
        "--output",
        output_path.as_posix(),
        "--tolerance-sec",
        "2.0",
        "--force",
    ]


def calculate_pacing(observed_payload: dict[str, Any]) -> dict[str, float] | None:
    events = observed_payload.get("events") or []
    usable = [
        event
        for event in events
        if event.get("event_ts") is not None and event.get("reader_frame_time") is not None
    ]
    if len(usable) < 2:
        return None
    first = usable[0]
    last = usable[-1]
    source_delta = float(last["event_ts"]) - float(first["event_ts"])
    wall_delta = float(last["reader_frame_time"]) - float(first["reader_frame_time"])
    if source_delta <= 0:
        return None
    return {
        "first_event_ts": round(float(first["event_ts"]), 3),
        "last_event_ts": round(float(last["event_ts"]), 3),
        "wall_delta_sec": wall_delta,
        "source_delta_sec": source_delta,
        "wall_per_source": wall_delta / source_delta,
    }


def build_validation_report(
    *,
    manifest: dict[str, Any],
    observed_payload: dict[str, Any] | None,
    comparison_payload: dict[str, Any] | None,
    commands: dict[str, list[str]],
) -> dict[str, Any]:
    proof_summary = dict(manifest.get("proof_summary") or {})
    if comparison_payload is not None:
        proof_summary.update(
            {
                "observed_event_count": comparison_payload.get("observed_event_count"),
                "matched_count": comparison_payload.get("matched_count"),
                "missing_truth_count": comparison_payload.get("missing_truth_count"),
                "unexpected_observed_count": comparison_payload.get("unexpected_observed_count"),
                "first_divergence": comparison_payload.get("first_divergence"),
            }
        )
    if observed_payload is not None:
        pacing = calculate_pacing(observed_payload)
        if pacing is not None:
            proof_summary["wall_per_source"] = pacing["wall_per_source"]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": round(time.time(), 3),
        "case_id": manifest["case_id"],
        "status": manifest["status"],
        "video": manifest["video"],
        "truth": manifest["truth"],
        "runtime": manifest["runtime"],
        "proof_artifacts": manifest["proof_artifacts"],
        "proof_summary": proof_summary,
        "commands": commands,
    }


def _run_command(command: list[str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def run_validation(
    *,
    manifest_path: Path,
    backend_port: int | None,
    frontend_port: int | None,
    dry_run: bool,
    execute: bool,
    use_existing_artifacts: bool,
    auto_start: bool,
    skip_preview: bool,
    skip_launch: bool,
    skip_capture: bool,
    skip_compare: bool,
    output_path: Path | None,
    force: bool,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    paths = default_output_paths(manifest)
    if use_existing_artifacts:
        artifacts = manifest.get("proof_artifacts") or {}
        paths["observed_events"] = Path(artifacts["observed_events"])
        paths["comparison_report"] = Path(artifacts["comparison_report"])
    if output_path is not None:
        paths["validation_report"] = output_path

    commands = {
        "preview": build_preview_command(manifest, force=force),
        "launch": build_launch_command(manifest, backend_port=backend_port, frontend_port=frontend_port),
        "capture": build_capture_command(
            manifest,
            output_path=paths["observed_events"],
            backend_port=backend_port,
            auto_start=auto_start,
        ),
        "compare": build_compare_command(
            manifest,
            observed_events_path=paths["observed_events"],
            output_path=paths["comparison_report"],
        ),
    }

    if dry_run or not execute:
        return {
            "mode": "dry-run",
            "manifest_path": manifest_path.as_posix(),
            "outputs": {key: value.as_posix() for key, value in paths.items()},
            "commands": commands,
            "use_existing_artifacts": use_existing_artifacts,
        }

    if use_existing_artifacts:
        skip_preview = True
        skip_launch = True
        skip_capture = True
        skip_compare = True

    if not skip_preview:
        _run_command(commands["preview"])
    if not skip_launch:
        _run_command(commands["launch"])
    if not skip_capture:
        _run_command(commands["capture"])
    if not skip_compare:
        _run_command(commands["compare"])

    observed_payload = _read_json(paths["observed_events"]) if paths["observed_events"].exists() else None
    comparison_payload = _read_json(paths["comparison_report"]) if paths["comparison_report"].exists() else None
    report = build_validation_report(
        manifest=manifest,
        observed_payload=observed_payload,
        comparison_payload=comparison_payload,
        commands=commands,
    )
    if paths["validation_report"].exists() and not force:
        raise FileExistsError(paths["validation_report"])
    _write_json(paths["validation_report"], report)
    return {"mode": "execute", "validation_report": paths["validation_report"].as_posix(), "report": report}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or plan a manifest-backed Factory Vision video validation")
    parser.add_argument("--case-id")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path, default=Path("validation/registry.json"))
    parser.add_argument("--backend-port", type=int)
    parser.add_argument("--frontend-port", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--use-existing-artifacts", action="store_true")
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--skip-preview", action="store_true")
    parser.add_argument("--skip-launch", action="store_true")
    parser.add_argument("--skip-capture", action="store_true")
    parser.add_argument("--skip-compare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = resolve_manifest_path(
        case_id=args.case_id,
        manifest_path=args.manifest,
        registry_path=args.registry,
    )
    result = run_validation(
        manifest_path=manifest_path,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        dry_run=args.dry_run,
        execute=args.execute,
        use_existing_artifacts=args.use_existing_artifacts,
        auto_start=args.auto_start,
        skip_preview=args.skip_preview,
        skip_launch=args.skip_launch,
        skip_capture=args.skip_capture,
        skip_compare=args.skip_compare,
        output_path=args.output,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
