#!/usr/bin/env python3
"""Search Factory2 diagnostic subsets for better runtime-backed proof coverage."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.build_morning_proof_report import (
    DEFAULT_FP_REPORTS,
    DEFAULT_POSITIVE_REPORTS,
    build_report,
)

DEFAULT_RUNTIME_AUDIT = Path("data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_optimized_proof_set.json")
SCHEMA_VERSION = "factory2-optimized-proof-set-v1"


@dataclass(frozen=True)
class RuntimeCoverage:
    covered_count: int
    covered_timestamps: list[float]
    uncovered_timestamps: list[float]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime_event_timestamps(path: Path) -> list[float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    timestamps: list[float] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            timestamps.append(round(float(event["event_ts"]), 3))
        except (KeyError, TypeError, ValueError):
            continue
    return timestamps


def accepted_cluster_intervals(report: dict[str, Any]) -> list[dict[str, float | str]]:
    accepted_rows = (report.get("decision_receipt_index") or {}).get("accepted") or []
    intervals_by_cluster: dict[str, tuple[float, float]] = {}
    for index, row in enumerate(accepted_rows, start=1):
        if not isinstance(row, dict):
            continue
        timestamps = row.get("receipt_timestamps") or {}
        try:
            first = float(timestamps["first"])
            last = float(timestamps["last"])
        except (KeyError, TypeError, ValueError):
            continue
        if last < first:
            first, last = last, first
        cluster_id = str(row.get("accepted_cluster_id") or f"accepted-cluster-{index:03d}")
        prior = intervals_by_cluster.get(cluster_id)
        if prior is None:
            intervals_by_cluster[cluster_id] = (first, last)
            continue
        intervals_by_cluster[cluster_id] = (min(prior[0], first), max(prior[1], last))
    return [
        {
            "accepted_cluster_id": cluster_id,
            "start_timestamp": interval[0],
            "end_timestamp": interval[1],
        }
        for cluster_id, interval in sorted(intervals_by_cluster.items(), key=lambda item: (item[1][0], item[1][1], item[0]))
    ]


def runtime_coverage(*, intervals: list[dict[str, float | str]], runtime_event_timestamps: list[float], tolerance_seconds: float) -> RuntimeCoverage:
    covered_timestamps: list[float] = []
    uncovered_timestamps: list[float] = []
    for timestamp in runtime_event_timestamps:
        covered = False
        for interval in intervals:
            start_timestamp = float(interval["start_timestamp"])
            end_timestamp = float(interval["end_timestamp"])
            if start_timestamp - tolerance_seconds <= timestamp <= end_timestamp + tolerance_seconds:
                covered = True
                break
        if covered:
            covered_timestamps.append(timestamp)
        else:
            uncovered_timestamps.append(timestamp)
    return RuntimeCoverage(
        covered_count=len(covered_timestamps),
        covered_timestamps=covered_timestamps,
        uncovered_timestamps=uncovered_timestamps,
    )


def default_evaluator(diagnostic_paths: list[Path]) -> dict[str, Any]:
    return build_report(
        diagnostic_paths=diagnostic_paths,
        fp_report_paths=[Path(path) for path in DEFAULT_FP_REPORTS],
        positive_report_paths=[Path(path) for path in DEFAULT_POSITIVE_REPORTS],
    )


def optimize_proof_set(
    *,
    base_diagnostic_paths: list[Path],
    candidate_diagnostic_paths: list[Path],
    runtime_event_timestamps: list[float],
    output_path: Path,
    tolerance_seconds: float,
    force: bool,
    evaluator: Callable[[list[Path]], dict[str, Any]] = default_evaluator,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")
    if len(candidate_diagnostic_paths) > 16:
        raise ValueError("candidate_diagnostic_paths is too large for exhaustive search")

    ranked_rows: list[dict[str, Any]] = []
    for count in range(len(candidate_diagnostic_paths) + 1):
        for combo in itertools.combinations(candidate_diagnostic_paths, count):
            selected_paths = list(base_diagnostic_paths) + list(combo)
            report = evaluator(selected_paths)
            intervals = accepted_cluster_intervals(report)
            coverage = runtime_coverage(
                intervals=intervals,
                runtime_event_timestamps=runtime_event_timestamps,
                tolerance_seconds=tolerance_seconds,
            )
            ranked_rows.append(
                {
                    "diagnostic_paths": [str(path) for path in selected_paths],
                    "selected_candidate_paths": [str(path) for path in combo],
                    "diagnostic_count": len(selected_paths),
                    "covered_runtime_events": coverage.covered_count,
                    "covered_runtime_timestamps": coverage.covered_timestamps,
                    "uncovered_runtime_timestamps": coverage.uncovered_timestamps,
                    "accepted_count": int(report.get("accepted_count") or 0),
                    "accepted_receipt_count": int(report.get("accepted_receipt_count") or 0),
                    "accepted_duplicate_receipt_count": int(report.get("accepted_duplicate_receipt_count") or 0),
                    "suppressed_count": int(report.get("suppressed_count") or 0),
                    "uncertain_count": int(report.get("uncertain_count") or 0),
                    "accepted_cluster_intervals": intervals,
                }
            )

    ranked_rows.sort(
        key=lambda row: (
            -int(row["covered_runtime_events"]),
            -int(row["accepted_count"]),
            int(row["uncertain_count"]),
            int(row["suppressed_count"]),
            int(row["diagnostic_count"]),
            row["selected_candidate_paths"],
        )
    )
    best = ranked_rows[0] if ranked_rows else {}
    result = {
        "schema_version": SCHEMA_VERSION,
        "runtime_event_timestamps": runtime_event_timestamps,
        "runtime_event_count": len(runtime_event_timestamps),
        "tolerance_seconds": tolerance_seconds,
        "base_diagnostic_paths": [str(path) for path in base_diagnostic_paths],
        "candidate_diagnostic_paths": [str(path) for path in candidate_diagnostic_paths],
        "evaluated_subset_count": len(ranked_rows),
        "selected_diagnostic_paths": best.get("diagnostic_paths") or [],
        "selected_candidate_paths": best.get("selected_candidate_paths") or [],
        "summary": {
            "covered_runtime_events": best.get("covered_runtime_events"),
            "uncovered_runtime_timestamps": best.get("uncovered_runtime_timestamps") or [],
            "accepted_count": best.get("accepted_count"),
            "accepted_receipt_count": best.get("accepted_receipt_count"),
            "accepted_duplicate_receipt_count": best.get("accepted_duplicate_receipt_count"),
            "suppressed_count": best.get("suppressed_count"),
            "uncertain_count": best.get("uncertain_count"),
            "diagnostic_count": best.get("diagnostic_count"),
        },
        "top_ranked_subsets": ranked_rows[:10],
    }
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize a Factory2 proof diagnostic subset against runtime event coverage")
    parser.add_argument("--runtime-audit", type=Path, default=DEFAULT_RUNTIME_AUDIT)
    parser.add_argument("--base-diagnostic", action="append", dest="base_diagnostics", required=True)
    parser.add_argument("--candidate-diagnostic", action="append", dest="candidate_diagnostics", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tolerance-seconds", type=float, default=0.5)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = optimize_proof_set(
        base_diagnostic_paths=[Path(path) for path in args.base_diagnostics],
        candidate_diagnostic_paths=[Path(path) for path in args.candidate_diagnostics],
        runtime_event_timestamps=load_runtime_event_timestamps(args.runtime_audit),
        output_path=args.output,
        tolerance_seconds=args.tolerance_seconds,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "covered_runtime_events": result["summary"]["covered_runtime_events"],
                "runtime_event_count": result["runtime_event_count"],
                "accepted_count": result["summary"]["accepted_count"],
                "uncertain_count": result["summary"]["uncertain_count"],
                "selected_candidate_paths": result["selected_candidate_paths"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
