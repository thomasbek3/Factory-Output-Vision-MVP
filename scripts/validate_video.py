#!/usr/bin/env python3
"""CLI wrapper for the manifest-backed real-app validation workflow.

The orchestration moved to app/services/validation_runner.py (CP6 inversion:
app modules must not import from scripts.*). This file keeps the command-line
interface stable: same flags, same behavior, same output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Re-exported for backwards compatibility: tests and app code import these
# from scripts.validate_video.
from app.services.validation_runner import (  # noqa: F401
    REPORT_SCHEMA_VERSION,
    build_capture_command,
    build_compare_command,
    build_launch_command,
    build_preview_command,
    build_validation_report,
    calculate_pacing,
    default_output_paths,
    resolve_manifest_path,
    run_validation,
)


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
    registry_path = args.registry if args.registry.is_absolute() else REPO_ROOT / args.registry
    manifest_path = resolve_manifest_path(
        case_id=args.case_id,
        manifest_path=args.manifest,
        registry_path=registry_path,
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
