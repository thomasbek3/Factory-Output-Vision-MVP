from __future__ import annotations

import copy
import importlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "validation/learning_registry.json"
REQUIRED_OUTPUT_FIELDS = {
    "case_id",
    "status",
    "aliases",
    "readiness",
    "best_next_action",
    "commands",
    "do_not_trust",
    "related_cases",
    "artifact_warnings",
    "dataset_export",
    "trust_boundaries",
    "blocked_reasons",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(args: list[str]) -> tuple[int, str, str]:
    try:
        factory_learn = importlib.import_module("scripts.factory_learn")
    except ModuleNotFoundError as exc:
        raise AssertionError("scripts.factory_learn is not importable") from exc

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = factory_learn.main(args)
    return rc, stdout.getvalue(), stderr.getvalue()


def _registry_with_case_update(case_id: str, updates: dict[str, Any], tmp_path: Path) -> Path:
    registry = _read_json(REGISTRY_PATH)
    registry = copy.deepcopy(registry)
    for case in registry["cases"]:
        if case["case_id"] == case_id:
            case.update(updates)
            break
    else:
        raise AssertionError(f"case not found: {case_id}")

    path = tmp_path / "learning_registry.json"
    path.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_recommend_factory2_json_contains_required_contract_fields() -> None:
    rc, stdout, stderr = _run(["recommend", "--case-id", "factory2_test_case_1", "--format", "json"])

    assert rc == 0, stderr
    payload = json.loads(stdout)
    assert REQUIRED_OUTPUT_FIELDS <= set(payload)
    assert payload["case_id"] == "factory2_test_case_1"
    assert payload["status"] == "verified_app_proof"
    assert payload["readiness"]["validation"] == "verified"
    assert payload["trust_boundaries"]["promotion_eligible"] is True
    assert payload["artifact_warnings"] == []
    assert payload["commands"]
    assert payload["do_not_trust"]


def test_recommend_resolves_factory2_alias() -> None:
    rc, stdout, stderr = _run(["recommend", "--case-id", "factory2", "--format", "json"])

    assert rc == 0, stderr
    payload = json.loads(stdout)
    assert payload["case_id"] == "factory2_test_case_1"
    assert "factory2" in payload["aliases"]


def test_recommend_real_factory_reports_blockers_and_missing_artifacts() -> None:
    rc, stdout, stderr = _run(["recommend", "--case-id", "real_factory_candidate", "--format", "json"])

    assert rc == 0, stderr
    payload = json.loads(stdout)
    assert payload["case_id"] == "real_factory_candidate"
    assert payload["status"] == "diagnostic_recovered"
    assert payload["readiness"]["validation"] == "blocked"
    assert payload["readiness"]["training"] == "blocked"
    assert payload["trust_boundaries"]["validation_truth_eligible"] is False
    assert payload["dataset_export"]["state"] == "blocked"
    assert any("bronze" in item.lower() for item in payload["do_not_trust"])
    assert any("validation truth" in item.lower() for item in payload["do_not_trust"])
    assert any("reviewed_gold_truth_missing" == reason for reason in payload["blocked_reasons"])
    assert any(
        warning["path"] == "data/calibration/real_factory_placed_and_stayed_v1.json"
        and "runtime" in warning["affects"]
        for warning in payload["artifact_warnings"]
    )


def test_recommend_text_renders_same_core_facts() -> None:
    rc, stdout, stderr = _run(["recommend", "--case-id", "factory2", "--format", "text"])

    assert rc == 0, stderr
    assert "Case: factory2_test_case_1" in stdout
    assert "Status: verified_app_proof" in stdout
    assert "Readiness:" in stdout
    assert "Best next action:" in stdout
    assert "Do not trust:" in stdout
    assert "Commands:" in stdout


def test_recommend_unknown_case_fails_nonzero_and_lists_known_ids() -> None:
    rc, stdout, stderr = _run(["recommend", "--case-id", "not_a_case", "--format", "json"])

    assert rc != 0
    assert stdout == ""
    assert "Unknown case_id or alias: not_a_case" in stderr
    assert "Known case IDs:" in stderr
    assert "factory2_test_case_1" in stderr
    assert "real_factory_candidate" in stderr


def test_recommend_rejects_invalid_promotion_trust_claim(tmp_path: Path) -> None:
    registry_path = _registry_with_case_update(
        "real_factory_candidate",
        {
            "trust_boundaries": {
                "runtime_observation_allowed": True,
                "validation_truth_eligible": False,
                "training_eligible": False,
                "promotion_eligible": True,
            }
        },
        tmp_path,
    )

    rc, stdout, stderr = _run(
        [
            "recommend",
            "--case-id",
            "real_factory_candidate",
            "--registry",
            str(registry_path),
            "--format",
            "json",
        ]
    )

    assert rc != 0
    assert stdout == ""
    assert "promotion_eligible requires validation_truth_eligible" in stderr


def test_recommend_missing_required_evidence_artifact_blocks_readiness(tmp_path: Path) -> None:
    registry = _read_json(REGISTRY_PATH)
    registry = copy.deepcopy(registry)
    case = next(entry for entry in registry["cases"] if entry["case_id"] == "factory2_test_case_1")
    case["evidence_refs"][0]["path"] = "data/reports/does_not_exist.required.json"
    case["evidence_refs"][0]["affects"] = ["validation", "promotion"]

    registry_path = tmp_path / "learning_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")

    rc, stdout, stderr = _run(
        [
            "recommend",
            "--case-id",
            "factory2_test_case_1",
            "--registry",
            str(registry_path),
            "--format",
            "json",
        ]
    )

    assert rc == 0, stderr
    payload = json.loads(stdout)
    assert payload["readiness"]["validation"] == "blocked"
    assert payload["readiness"]["promotion"] == "blocked"
    assert any(
        warning["path"] == "data/reports/does_not_exist.required.json"
        and warning["reason"] == "required_artifact_missing"
        and warning["affects"] == ["validation", "promotion"]
        for warning in payload["artifact_warnings"]
    )
