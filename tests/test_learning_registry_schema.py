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


def test_learning_registry_has_required_top_level_shape() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    schema = _read_json(REPO_ROOT / "validation/schemas/learning_registry.schema.json")

    _assert_required(registry, schema)
    assert registry["schema_version"] == "factory-vision-learning-registry-v1"
    assert registry["artifact_root"] == "/Users/thomas/FactoryVisionArtifacts"
    assert registry["policy"]["runtime_count_authority"] == "yolo_event_app_path_only"
    assert registry["policy"]["teacher_label_default_tier"] == "bronze_pending"
    assert registry["policy"]["validation_truth_rule"] == "reviewed_gold_truth_required"
    assert registry["policy"]["cloud_upload_default"] == "forbidden_without_explicit_permission"


def test_real_factory_is_failed_learning_case_not_verified_case() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    cases = {entry["case_id"]: entry for entry in registry["cases"]}
    real_factory = cases["real_factory_candidate"]

    assert real_factory["status"] == "failed_diagnostic"
    assert real_factory["privacy_mode"] == "offline_local"
    assert real_factory["manifest_path"] == "validation/test_cases/real_factory.json"

    outcome = real_factory["learning_outcome"]
    assert outcome["blind_prediction_status"] == "no_valid_blind_prediction"
    assert outcome["hidden_human_total"] == 4
    assert outcome["failed_diagnostic_total"] == 18
    assert outcome["observed_minus_human_delta"] == 14
    assert outcome["registry_promotion_eligible"] is False
    assert outcome["validation_truth_eligible"] is False
    assert outcome["training_eligible"] is False


def test_learning_registry_points_to_existing_real_factory_artifacts() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    real_factory = next(entry for entry in registry["cases"] if entry["case_id"] == "real_factory_candidate")

    assert (REPO_ROOT / real_factory["manifest_path"]).exists()

    artifacts = real_factory["artifact_paths"]
    direct_paths = [
        value
        for value in artifacts.values()
        if isinstance(value, str) and value.startswith(("data/", "validation/"))
    ]
    list_paths = [
        item
        for value in artifacts.values()
        if isinstance(value, list)
        for item in value
        if isinstance(item, str) and item.startswith(("data/", "validation/"))
    ]
    for artifact_path in direct_paths + list_paths:
        assert (REPO_ROOT / artifact_path).exists(), artifact_path

    viability = _read_json(REPO_ROOT / artifacts["blind_prediction_viability"])
    assert viability["status"] == "no_valid_blind_prediction"
    assert viability["numeric_prediction_allowed"] is False
