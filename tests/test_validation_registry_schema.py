from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_required(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    for key in schema.get("required", []):
        assert key in payload, f"missing required key {key}"


def test_validation_registry_points_to_valid_case_manifests() -> None:
    registry = _read_json(REPO_ROOT / "validation/registry.json")
    assert registry["schema_version"] == "factory-vision-validation-registry-v1"

    case_ids = {entry["case_id"] for entry in registry["cases"]}
    assert case_ids == {
        "factory2_test_case_1",
        "img3262_candidate",
        "img3254_clean22_candidate",
    }

    manifest_schema = _read_json(REPO_ROOT / "validation/schemas/video_manifest.schema.json")
    for entry in registry["cases"]:
        manifest_path = REPO_ROOT / entry["manifest_path"]
        assert manifest_path.exists(), entry["manifest_path"]
        manifest = _read_json(manifest_path)
        _assert_required(manifest, manifest_schema)
        assert manifest["case_id"] == entry["case_id"]
        assert manifest["status"] == entry["status"]
        assert manifest["truth"]["expected_total"] == entry["expected_total"]
        assert manifest["video"]["sha256"] == entry["video_sha256"]


def test_verified_manifests_reference_clean_app_proof_artifacts() -> None:
    registry = _read_json(REPO_ROOT / "validation/registry.json")
    for entry in registry["cases"]:
        manifest = _read_json(REPO_ROOT / entry["manifest_path"])
        summary = manifest["proof_summary"]
        expected_total = manifest["truth"]["expected_total"]

        assert manifest["runtime"]["demo_count_mode"] == "live_reader_snapshot"
        assert manifest["runtime"]["counting_mode"] == "event_based"
        assert manifest["runtime"]["playback_speed"] == 1.0
        assert summary["observed_event_count"] == expected_total
        assert summary["matched_count"] == expected_total
        assert summary["missing_truth_count"] == 0
        assert summary["unexpected_observed_count"] == 0
        assert summary["first_divergence"] is None
        assert abs(float(summary["wall_per_source"]) - 1.0) < 0.01

        artifacts = manifest["proof_artifacts"]
        for key in ("observed_events", "comparison_report", "validation_report"):
            artifact_path = REPO_ROOT / artifacts[key]
            assert artifact_path.exists(), artifacts[key]

        comparison = _read_json(REPO_ROOT / artifacts["comparison_report"])
        assert comparison["matched_count"] == summary["matched_count"]
        assert comparison["missing_truth_count"] == 0
        assert comparison["unexpected_observed_count"] == 0
        assert comparison["first_divergence"] is None


def test_validation_artifact_schemas_are_present_and_have_required_keys() -> None:
    schema_names = [
        "video_manifest.schema.json",
        "truth_ledger.schema.json",
        "app_run.schema.json",
        "comparison_report.schema.json",
        "validation_report.schema.json",
    ]
    for name in schema_names:
        schema = _read_json(REPO_ROOT / "validation/schemas" / name)
        assert schema["type"] == "object"
        assert schema["required"]
