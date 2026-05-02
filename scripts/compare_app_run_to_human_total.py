#!/usr/bin/env python3
"""Compare an observed app run against a total-only human count."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "app-run-vs-human-total-comparison-v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare_app_run_to_human_total(
    *,
    human_total_path: Path,
    observed_events_path: Path,
    output_path: Path,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    human_payload = _read_json(human_total_path)
    observed_payload = _read_json(observed_events_path)
    expected_total = int(human_payload["expected_human_total"])
    observed_total = int(observed_payload.get("observed_event_count") or len(observed_payload.get("events") or []))
    delta = observed_total - expected_total
    payload = {
        "schema_version": SCHEMA_VERSION,
        "human_total_path": str(human_total_path),
        "observed_events_path": str(observed_events_path),
        "verification_level": "total_only",
        "expected_human_total": expected_total,
        "observed_event_count": observed_total,
        "delta": delta,
        "total_matches": delta == 0,
        "observed_run_complete": bool(observed_payload.get("run_complete")),
        "observed_coverage_end_sec": observed_payload.get("observed_coverage_end_sec"),
        "warning": (
            "Total-only comparison cannot prove event-level correctness. "
            "Use a timestamped truth ledger before promoting this to a verified test case."
        ),
    }
    _write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare app observed event count to a total-only human count")
    parser.add_argument("--human-total", type=Path, required=True)
    parser.add_argument("--observed-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = compare_app_run_to_human_total(
        human_total_path=args.human_total,
        observed_events_path=args.observed_events,
        output_path=args.output,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "expected_human_total": payload["expected_human_total"],
                "observed_event_count": payload["observed_event_count"],
                "total_matches": payload["total_matches"],
            }
        )
    )


if __name__ == "__main__":
    main()
