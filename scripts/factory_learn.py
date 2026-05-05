"""Learning-library registry helper commands."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "validation/learning_registry.json"
EXPECTED_SCHEMA_VERSION = "factory-vision-learning-registry-v2"
NON_TRUTH_AUTHORITIES = {
    "diagnostic",
    "review_scaffold",
    "teacher_suggestion",
    "training_artifact",
}


class LearningRegistryError(ValueError):
    """Raised when the learning registry cannot produce a safe recommendation."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_artifact(path_text: str, *, repo_root: Path, artifact_root: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    repo_path = repo_root / path
    if repo_path.exists():
        return repo_path
    return artifact_root / path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LearningRegistryError(message)


def validate_registry(registry: dict[str, Any]) -> None:
    _require(
        registry.get("schema_version") == EXPECTED_SCHEMA_VERSION,
        f"learning registry must use {EXPECTED_SCHEMA_VERSION}",
    )
    _require(isinstance(registry.get("cases"), list), "learning registry cases must be a list")

    seen_ids: set[str] = set()
    seen_aliases: set[str] = set()
    for case in registry["cases"]:
        case_id = str(case.get("case_id") or "")
        _require(case_id, "learning registry case is missing case_id")
        _require(case_id not in seen_ids, f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)

        for alias in case.get("aliases", []):
            _require(alias not in seen_aliases, f"duplicate learning registry alias: {alias}")
            _require(alias not in seen_ids, f"alias collides with case_id: {alias}")
            seen_aliases.add(str(alias))

        trust = case.get("trust_boundaries") or {}
        if trust.get("promotion_eligible") and not trust.get("validation_truth_eligible"):
            raise LearningRegistryError(
                f"{case_id}: promotion_eligible requires validation_truth_eligible"
            )
        if trust.get("training_eligible") and (case.get("dataset_export") or {}).get("state") != "ready":
            raise LearningRegistryError(f"{case_id}: training_eligible requires dataset_export.state=ready")

        for evidence in case.get("evidence_refs", []):
            artifact_id = evidence.get("artifact_id", evidence.get("path", "<unknown>"))
            prefix = f"{case_id}:{artifact_id}"
            if evidence.get("promotion_eligible") and not evidence.get("validation_truth_eligible"):
                raise LearningRegistryError(
                    f"{prefix}: promotion_eligible requires validation_truth_eligible"
                )
            if evidence.get("promotion_eligible") and evidence.get("authority") != "canonical_proof":
                raise LearningRegistryError(f"{prefix}: promotion evidence must be canonical_proof")
            if evidence.get("authority") in NON_TRUTH_AUTHORITIES:
                if evidence.get("validation_truth_eligible"):
                    raise LearningRegistryError(
                        f"{prefix}: {evidence.get('authority')} cannot be validation truth"
                    )
                if evidence.get("promotion_eligible"):
                    raise LearningRegistryError(
                        f"{prefix}: {evidence.get('authority')} cannot support promotion"
                    )


def case_lookup(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for case in registry["cases"]:
        lookup[case["case_id"]] = case
        for alias in case.get("aliases", []):
            lookup[alias] = case
    return lookup


def known_case_ids(registry: dict[str, Any]) -> list[str]:
    return sorted(case["case_id"] for case in registry["cases"])


def _record_missing_artifact(
    *,
    path: str,
    affects: list[str],
    readiness: dict[str, str],
    artifact_warnings: list[dict[str, Any]],
    blocked_reasons: list[str],
) -> None:
    warning = {
        "path": path,
        "reason": "required_artifact_missing",
        "affects": affects,
    }
    if warning not in artifact_warnings:
        artifact_warnings.append(warning)

    for affected in affects:
        if affected in readiness:
            readiness[affected] = "blocked"

    blocker = f"missing_required_artifact:{path}"
    if blocker not in blocked_reasons:
        blocked_reasons.append(blocker)


def build_recommendation(
    *,
    case: dict[str, Any],
    repo_root: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    readiness = copy.deepcopy(case["readiness"])
    blocked_reasons = list(case.get("blocked_reasons", []))
    artifact_warnings: list[dict[str, Any]] = []

    for evidence in case.get("evidence_refs", []):
        if evidence.get("must_exist", True):
            path = evidence["path"]
            if not resolve_artifact(path, repo_root=repo_root, artifact_root=artifact_root).exists():
                _record_missing_artifact(
                    path=path,
                    affects=list(evidence.get("affects", [])),
                    readiness=readiness,
                    artifact_warnings=artifact_warnings,
                    blocked_reasons=blocked_reasons,
                )

    commands: list[dict[str, Any]] = []
    for command in case.get("commands", []):
        output_command = {
            "label": command["label"],
            "command": command["command"],
            "prerequisites": [item["path"] for item in command.get("prerequisites", [])],
            "exists": True,
        }
        for prereq in command.get("prerequisites", []):
            if not prereq.get("required", True):
                continue
            path = prereq["path"]
            if not resolve_artifact(path, repo_root=repo_root, artifact_root=artifact_root).exists():
                output_command["exists"] = False
                _record_missing_artifact(
                    path=path,
                    affects=list(prereq.get("affects", [])),
                    readiness=readiness,
                    artifact_warnings=artifact_warnings,
                    blocked_reasons=blocked_reasons,
                )
        commands.append(output_command)

    return {
        "case_id": case["case_id"],
        "status": case["status"],
        "aliases": list(case.get("aliases", [])),
        "readiness": readiness,
        "best_next_action": case["best_next_action"],
        "commands": commands,
        "do_not_trust": list(case.get("do_not_trust", [])),
        "related_cases": copy.deepcopy(case.get("related_cases", [])),
        "artifact_warnings": artifact_warnings,
        "dataset_export": copy.deepcopy(case["dataset_export"]),
        "trust_boundaries": copy.deepcopy(case["trust_boundaries"]),
        "blocked_reasons": blocked_reasons,
    }


def render_text(recommendation: dict[str, Any]) -> str:
    lines = [
        f"Case: {recommendation['case_id']}",
        f"Status: {recommendation['status']}",
        f"Aliases: {', '.join(recommendation['aliases']) or '(none)'}",
        "Readiness:",
    ]
    for key in ("runtime", "validation", "training", "promotion"):
        lines.append(f"  {key}: {recommendation['readiness'][key]}")

    lines.extend(
        [
            f"Best next action: {recommendation['best_next_action']}",
            "Blocked reasons:",
        ]
    )
    if recommendation["blocked_reasons"]:
        lines.extend(f"  - {reason}" for reason in recommendation["blocked_reasons"])
    else:
        lines.append("  - (none)")

    lines.append("Artifact warnings:")
    if recommendation["artifact_warnings"]:
        for warning in recommendation["artifact_warnings"]:
            affects = ", ".join(warning["affects"])
            lines.append(f"  - {warning['path']} ({warning['reason']}; affects: {affects})")
    else:
        lines.append("  - (none)")

    lines.append("Do not trust:")
    lines.extend(f"  - {item}" for item in recommendation["do_not_trust"])

    lines.append("Commands:")
    for command in recommendation["commands"]:
        state = "ready" if command["exists"] else "blocked"
        lines.append(f"  - {command['label']} [{state}]")
        lines.append(f"    {command['command']}")
        if command["prerequisites"]:
            lines.append(f"    prerequisites: {', '.join(command['prerequisites'])}")

    return "\n".join(lines) + "\n"


def recommend(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    registry = read_json(registry_path)
    validate_registry(registry)
    lookup = case_lookup(registry)
    case = lookup.get(args.case_id)
    if case is None:
        known = ", ".join(known_case_ids(registry))
        raise LearningRegistryError(f"Unknown case_id or alias: {args.case_id}\nKnown case IDs: {known}")

    artifact_root = Path(registry["artifact_root"])
    recommendation = build_recommendation(
        case=case,
        repo_root=REPO_ROOT,
        artifact_root=artifact_root,
    )
    if args.format == "json":
        print(json.dumps(recommendation, indent=2, sort_keys=True))
    else:
        print(render_text(recommendation), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Factory Vision learning-library cases")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Recommend the next safe action for a learning-library case",
    )
    recommend_parser.add_argument("--case-id", required=True, help="Case ID or alias")
    recommend_parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY_PATH),
        help="Path to validation/learning_registry.json",
    )
    recommend_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    recommend_parser.set_defaults(func=recommend)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LearningRegistryError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
