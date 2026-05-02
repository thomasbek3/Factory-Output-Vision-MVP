#!/usr/bin/env python3
"""Register a validation manifest in validation/registry.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA_VERSION = "factory-vision-validation-registry-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation_truth_guard import validate_truth_file


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_relative(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_registry_entry(*, manifest: dict[str, Any], manifest_path: Path, repo_root: Path) -> dict[str, Any]:
    proof_artifacts = manifest.get("proof_artifacts") or {}
    truth = manifest.get("truth") or {}
    video = manifest.get("video") or {}
    return {
        "case_id": manifest["case_id"],
        "display_name": manifest.get("display_name", manifest["case_id"]),
        "status": manifest["status"],
        "promotion_status": manifest.get("promotion_status", "not_promoted"),
        "expected_total": truth.get("expected_total"),
        "truth_rule_id": truth.get("rule_id"),
        "video_sha256": video.get("sha256"),
        "manifest_path": _repo_relative(manifest_path, repo_root=repo_root),
        "comparison_report_path": proof_artifacts.get("comparison_report"),
        "last_verified_at": manifest.get("verified_at"),
    }


def upsert_registry_entry(
    *,
    registry: dict[str, Any],
    entry: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    if registry.get("schema_version") not in (None, REGISTRY_SCHEMA_VERSION):
        raise ValueError(f"unsupported registry schema: {registry.get('schema_version')}")
    registry.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    cases = list(registry.get("cases") or [])
    index = next((idx for idx, item in enumerate(cases) if item.get("case_id") == entry["case_id"]), None)
    if index is not None and not force:
        raise FileExistsError(f"case already exists in registry: {entry['case_id']}")
    if index is None:
        cases.append(entry)
    else:
        cases[index] = entry
    cases.sort(key=lambda item: str(item.get("case_id") or ""))
    registry["cases"] = cases
    return registry


def register_manifest(
    *,
    manifest_path: Path,
    registry_path: Path,
    repo_root: Path,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    validate_truth_file(Path(manifest["truth"]["truth_ledger_path"]), repo_root=repo_root)
    if registry_path.exists():
        registry = _read_json(registry_path)
    else:
        registry = {"schema_version": REGISTRY_SCHEMA_VERSION, "cases": []}
    entry = build_registry_entry(manifest=manifest, manifest_path=manifest_path, repo_root=repo_root)
    updated = upsert_registry_entry(registry=registry, entry=entry, force=force)
    if not dry_run:
        _write_json(registry_path, updated)
    return {"entry": entry, "registry": updated}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a Factory Vision validation manifest")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("validation/registry.json"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = register_manifest(
        manifest_path=args.manifest,
        registry_path=args.registry,
        repo_root=args.repo_root,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps({"case_id": result["entry"]["case_id"], "registry": str(args.registry), "dry_run": args.dry_run}))


if __name__ == "__main__":
    main()
