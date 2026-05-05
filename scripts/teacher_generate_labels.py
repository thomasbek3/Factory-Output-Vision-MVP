#!/usr/bin/env python3
"""Generate advisory teacher labels from event evidence without network calls by default."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


SCHEMA_VERSION = "factory-vision-teacher-labels-v1"
PROMPT_VERSION = "active-learning-teacher-dry-run-v1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TeacherProvider(Protocol):
    def provider_metadata(self) -> dict[str, Any]:
        ...

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DryRunFixtureProvider:
    name: str = "dry_run_fixture"
    model: str = "local-placeholder"

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "local_fixture",
            "model": self.model,
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        window_id = str(window["window_id"])
        return {
            "label_id": f"{window_id}-teacher-dry-run",
            "window_id": window_id,
            "teacher_output_status": "unclear",
            "suggested_event_ts_sec": window.get("time_window", {}).get("center_sec"),
            "confidence_tier": "low",
            "duplicate_risk": str(window.get("duplicate_risk") or "unknown"),
            "miss_risk": str(window.get("miss_risk") or "unknown"),
            "rationale": "Dry-run placeholder only. No visual model was called.",
            "label_authority_tier": "bronze",
            "review_status": "pending",
            "validation_truth_eligible": False,
            "training_eligible": False,
        }


def provider_for_name(name: str) -> TeacherProvider:
    if name in {"dry_run_fixture", "local_fixture"}:
        return DryRunFixtureProvider(name=name)
    raise ValueError(f"provider {name!r} is not implemented; default scripts make no network calls")


def build_teacher_labels(
    *,
    evidence_path: Path,
    provider: TeacherProvider,
) -> dict[str, Any]:
    evidence = read_json(evidence_path)
    labels = [provider.generate_label(window=window) for window in evidence.get("windows") or []]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": evidence["case_id"],
        "source_evidence_path": evidence_path.as_posix(),
        "privacy_mode": evidence.get("privacy_mode", "offline_local"),
        "provider": provider.provider_metadata(),
        "refuses_validation_truth": True,
        "labels": labels,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate advisory teacher labels from event evidence")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--provider", default="dry_run_fixture")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    provider = provider_for_name(args.provider)
    payload = build_teacher_labels(evidence_path=args.evidence, provider=provider)
    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": args.output.as_posix(), "label_count": len(payload["labels"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
