from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "docs/README.md",
    "docs/00_CURRENT_STATE.md",
    "docs/01_PRODUCT_SPEC.md",
    "docs/02_ARCHITECTURE.md",
    "docs/03_VALIDATION_PIPELINE.md",
    "docs/04_TEST_CASE_REGISTRY.md",
    "docs/06_DEVELOPER_RUNBOOK.md",
    "docs/09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md",
    "docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md",
    "docs/11_RELEASE_AND_VALIDATION_CHECKLIST.md",
    "docs/decisions/README.md",
    "validation/registry.json",
    "validation/learning_registry.json",
    ".github/pull_request_template.md",
]

REQUIRED_JSON = [
    "validation/registry.json",
    "validation/learning_registry.json",
    "validation/artifact_storage.json",
]

REQUIRED_DECISIONS = [
    "docs/decisions/0001-current-runtime-is-system-of-record.md",
    "docs/decisions/0002-validation-registry-is-promotion-gate.md",
    "docs/decisions/0003-detector-and-edge-stack-changes-are-evaluation-lanes.md",
    "docs/decisions/0004-vlm-and-teacher-models-are-audit-only.md",
]

FORBIDDEN_TRACKED_PATTERNS = [
    ".env",
    "*.pyc",
    "__pycache__/*",
    ".venv/*",
    "frontend/node_modules/*",
    "frontend/dist/*",
]

ARTIFACT_PREFIXES = (
    "data/",
    "datasets/",
    "models/",
    "training_frames/",
    "training_runs/",
)


def _git_ls_files() -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for relpath in REQUIRED_PATHS + REQUIRED_DECISIONS:
        if not (ROOT / relpath).exists():
            errors.append(f"missing required repo file: {relpath}")

    for relpath in REQUIRED_JSON:
        path = ROOT / relpath
        if not path.exists():
            errors.append(f"missing required JSON file: {relpath}")
            continue
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {relpath}: line {exc.lineno} column {exc.colno}: {exc.msg}")

    tracked = _git_ls_files()
    forbidden = [path for path in tracked if _matches_any(path, FORBIDDEN_TRACKED_PATTERNS)]
    if forbidden:
        errors.append("forbidden tracked files:\n  " + "\n  ".join(forbidden[:50]))

    tracked_artifacts = [path for path in tracked if path.startswith(ARTIFACT_PREFIXES)]
    if tracked_artifacts:
        warnings.append(
            f"{len(tracked_artifacts)} tracked artifact/cache paths exist. "
            "Do not delete them blindly; classify through docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md."
        )

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("Repo hygiene failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repo hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
