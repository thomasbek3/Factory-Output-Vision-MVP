from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "factory-vision-blind-replay-gate-v1"
ValidationRunner = Callable[..., dict[str, Any]]


def run_blind_replay_gate(
    *,
    manifest_path: Path,
    output_path: Path,
    execute: bool = False,
    backend_port: int | None = None,
    frontend_port: int | None = None,
    auto_start: bool = True,
    force: bool = False,
    validation_runner: ValidationRunner | None = None,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    runner = validation_runner or _run_manifest_validation
    validation_result = runner(
        manifest_path=manifest_path,
        backend_port=backend_port,
        frontend_port=frontend_port,
        dry_run=not execute,
        execute=execute,
        use_existing_artifacts=False,
        auto_start=auto_start,
        skip_preview=True,
        skip_launch=False,
        skip_capture=False,
        skip_compare=False,
        output_path=None,
        force=True,
    )
    payload = _build_gate_report(manifest_path=manifest_path, execute=execute, validation_result=validation_result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _run_manifest_validation(**kwargs: Any) -> dict[str, Any]:
    from app.services.validation_runner import run_validation

    return run_validation(**kwargs)


def _build_gate_report(*, manifest_path: Path, execute: bool, validation_result: dict[str, Any]) -> dict[str, Any]:
    report = validation_result.get("report") or {}
    proof_summary = report.get("proof_summary") or {}
    pass_reasons: list[str] = []
    fail_reasons: list[str] = []
    if not execute:
        fail_reasons.append("dry_run_does_not_pass_gate")
    if validation_result.get("mode") != "execute":
        fail_reasons.append("validation_runtime_not_executed")

    expected_total = ((report.get("truth") or {}).get("expected_total") if report else None)
    matched_count = proof_summary.get("matched_count")
    missing_truth_count = proof_summary.get("missing_truth_count")
    unexpected_observed_count = proof_summary.get("unexpected_observed_count")
    first_divergence = proof_summary.get("first_divergence")
    observed_event_count = proof_summary.get("observed_event_count")
    if execute and expected_total is not None and matched_count == expected_total:
        pass_reasons.append("matched_expected_total")
    elif execute:
        fail_reasons.append("matched_count_does_not_equal_expected_total")
    if execute and missing_truth_count == 0:
        pass_reasons.append("no_missing_truth")
    elif execute:
        fail_reasons.append("missing_truth_events")
    if execute and unexpected_observed_count == 0:
        pass_reasons.append("no_unexpected_observed")
    elif execute:
        fail_reasons.append("unexpected_observed_events")
    if execute and first_divergence is None:
        pass_reasons.append("no_first_divergence")
    elif execute:
        fail_reasons.append("first_divergence_present")

    passed = execute and not fail_reasons
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_path": str(manifest_path),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "count_authority": "existing_yolo_event_runtime_only",
        "teacher_labels_used_as_truth": False,
        "runtime_path": "app.services.validation_runner.run_validation",
        "validation_result_mode": validation_result.get("mode"),
        "validation_report_path": validation_result.get("validation_report"),
        "observed_event_count": observed_event_count,
        "expected_total": expected_total,
        "matched_count": matched_count,
        "missing_truth_count": missing_truth_count,
        "unexpected_observed_count": unexpected_observed_count,
        "first_divergence": first_divergence,
        "pass_reasons": pass_reasons,
        "fail_reasons": fail_reasons,
    }
