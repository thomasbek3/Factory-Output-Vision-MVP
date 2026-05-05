from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = Path("/Users/thomas/FactoryVisionArtifacts")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_required(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    for key in schema.get("required", []):
        assert key in payload, f"missing required key {key}"


def _cases_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["case_id"]: entry for entry in registry["cases"]}


def _resolve_artifact(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists():
        return repo_path
    return ARTIFACT_ROOT / path


def test_learning_registry_has_required_top_level_shape() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    schema = _read_json(REPO_ROOT / "validation/schemas/learning_registry.schema.json")

    _assert_required(registry, schema)
    assert schema["properties"]["schema_version"]["const"] == "factory-vision-learning-registry-v2"
    assert registry["schema_version"] == "factory-vision-learning-registry-v2"
    assert registry["artifact_root"] == "/Users/thomas/FactoryVisionArtifacts"
    assert registry["policy"]["runtime_count_authority"] == "yolo_event_app_path_only"
    assert registry["policy"]["teacher_label_default_tier"] == "bronze_pending"
    assert registry["policy"]["validation_truth_rule"] == "reviewed_gold_truth_required"
    assert registry["policy"]["cloud_upload_default"] == "forbidden_without_explicit_permission"


def test_learning_registry_contains_verified_factory2_and_real_factory_learning_case() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    cases = _cases_by_id(registry)

    assert {"factory2_test_case_1", "real_factory_candidate"} <= set(cases)

    factory2 = cases["factory2_test_case_1"]
    assert factory2["status"] == "verified_app_proof"
    assert "factory2" in factory2["aliases"]
    assert factory2["readiness"]["validation"] == "verified"
    assert factory2["readiness"]["runtime"] == "verified"
    assert factory2["trust_boundaries"]["validation_truth_eligible"] is True
    assert factory2["trust_boundaries"]["promotion_eligible"] is True

    real_factory = cases["real_factory_candidate"]

    assert real_factory["status"] == "diagnostic_recovered"
    assert "real_factory" in real_factory["aliases"]
    assert real_factory["privacy_mode"] == "offline_local"
    assert real_factory["source_video"]["path"] == "data/videos/from-pc/real_factory.MOV"
    assert (
        real_factory["source_video"]["sha256"]
        == "48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86"
    )
    assert real_factory["readiness"]["validation"] == "blocked"
    assert real_factory["readiness"]["training"] == "blocked"
    assert real_factory["readiness"]["promotion"] == "blocked"

    outcome = real_factory["learning_outcome"]
    assert outcome["blind_prediction_status"] == "no_valid_blind_prediction"
    assert outcome["hidden_human_total"] == 4
    assert outcome["failed_diagnostic_total"] == 18
    assert outcome["observed_minus_human_delta"] == 14
    assert real_factory["trust_boundaries"]["promotion_eligible"] is False
    assert real_factory["trust_boundaries"]["validation_truth_eligible"] is False
    assert real_factory["trust_boundaries"]["training_eligible"] is False


def test_learning_registry_trust_boundaries_fail_closed() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")
    for case in registry["cases"]:
        trust = case["trust_boundaries"]
        if trust["promotion_eligible"]:
            assert trust["validation_truth_eligible"], case["case_id"]
        if trust["training_eligible"]:
            assert case["dataset_export"]["state"] == "ready", case["case_id"]

        for evidence in case["evidence_refs"]:
            if evidence["authority"] in {
                "diagnostic",
                "review_scaffold",
                "teacher_suggestion",
                "training_artifact",
            }:
                assert evidence["validation_truth_eligible"] is False, evidence
                assert evidence["promotion_eligible"] is False, evidence
            if evidence["promotion_eligible"]:
                assert evidence["authority"] == "canonical_proof", evidence
                assert evidence["validation_truth_eligible"] is True, evidence


def test_learning_registry_points_to_required_existing_artifacts() -> None:
    registry = _read_json(REPO_ROOT / "validation/learning_registry.json")

    for case in registry["cases"]:
        assert (REPO_ROOT / case["manifest_path"]).exists(), case["manifest_path"]
        for evidence in case["evidence_refs"]:
            if evidence.get("must_exist", True):
                assert _resolve_artifact(evidence["path"]).exists(), evidence["path"]

    real_factory = _cases_by_id(registry)["real_factory_candidate"]
    viability_path = next(
        evidence["path"]
        for evidence in real_factory["evidence_refs"]
        if evidence["artifact_id"] == "blind_prediction_viability"
    )
    viability = _read_json(_resolve_artifact(viability_path))
    assert viability["status"] == "no_valid_blind_prediction"
    assert viability["numeric_prediction_allowed"] is False
