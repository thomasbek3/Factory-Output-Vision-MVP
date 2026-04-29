#!/usr/bin/env python3
"""Build a runtime-backed diagnostic set for the next Factory2 proof rerun."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_morning_proof_report import DEFAULT_DIAGNOSTICS

DEFAULT_QUEUE = Path("data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_runtime_backed_proof_set.gap45_recentdedupe.json")
SCHEMA_VERSION = "factory2-runtime-backed-proof-set-v1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_runtime_backed_proof_set(
    *,
    queue_path: Path,
    output_path: Path,
    default_diagnostic_paths: list[str],
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    queue = payload.get("queue") or []
    selected_paths = list(default_diagnostic_paths)
    added_paths: list[str] = []

    for row in queue:
        if not isinstance(row, dict):
            continue
        preferred_path = str(row.get("preferred_diagnostic_path") or "")
        if not preferred_path or preferred_path in selected_paths:
            continue
        selected_paths.append(preferred_path)
        added_paths.append(preferred_path)

    result = {
        "schema_version": SCHEMA_VERSION,
        "queue_path": str(queue_path),
        "default_diagnostic_count": len(default_diagnostic_paths),
        "added_diagnostic_count": len(added_paths),
        "diagnostic_count": len(selected_paths),
        "default_diagnostic_paths": list(default_diagnostic_paths),
        "added_diagnostic_paths": added_paths,
        "diagnostic_paths": selected_paths,
    }
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a runtime-backed Factory2 proof diagnostic set")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_runtime_backed_proof_set(
        queue_path=args.queue,
        output_path=args.output,
        default_diagnostic_paths=list(DEFAULT_DIAGNOSTICS),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "default_diagnostic_count": payload["default_diagnostic_count"],
                "added_diagnostic_count": payload["added_diagnostic_count"],
                "diagnostic_count": payload["diagnostic_count"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
