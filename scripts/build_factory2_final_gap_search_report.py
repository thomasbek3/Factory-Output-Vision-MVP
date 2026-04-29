#!/usr/bin/env python3
"""Score Factory2 final-gap search diagnostics against fresh source-lineage criteria."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_morning_proof_report import DEFAULT_FP_REPORTS, DEFAULT_POSITIVE_REPORTS, build_report

DEFAULT_SEARCH_RUN = Path("data/reports/factory2_final_gap_search_run.v1.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_final_gap_search_report.v1.json")
SCHEMA_VERSION = "factory2-final-gap-search-report-v1"
ReportBuilder = Callable[..., dict[str, Any]]
FRESH_EVENT_SLACK_SECONDS = 0.75


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def receipt_interval(row: dict[str, Any]) -> tuple[float, float] | None:
    timestamps = row.get("receipt_timestamps") or {}
    try:
        first = float(timestamps.get("first"))
        last = float(timestamps.get("last"))
    except (TypeError, ValueError):
        return None
    if last < first:
        first, last = last, first
    return first, last


def interval_distance_to_event(row: dict[str, Any], event_ts: float) -> float:
    interval = receipt_interval(row)
    if interval is None:
        return float("inf")
    first, last = interval
    if first <= event_ts <= last:
        return 0.0
    return min(abs(event_ts - first), abs(event_ts - last))


def select_closest(rows: list[dict[str, Any]], event_ts: float) -> dict[str, Any] | None:
    if not rows:
        return None
    ordered = sorted(
        rows,
        key=lambda row: (
            interval_distance_to_event(row, event_ts),
            str(row.get("diagnostic_path") or ""),
            int(row.get("track_id") or 0),
        ),
    )
    return ordered[0]


def is_output_only_stub(row: dict[str, Any]) -> bool:
    reason = str(row.get("reason") or "")
    failure_link = str(row.get("failure_link") or "")
    return reason in {"static_stack_edge", "output_only_no_source_token"} or failure_link == "static_stack_or_resident_output"


def build_final_gap_search_report(
    *,
    search_run_path: Path,
    output_path: Path,
    report_builder: ReportBuilder = build_report,
    fp_report_paths: list[Path] | None = None,
    positive_report_paths: list[Path] | None = None,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    search_run = json.loads(search_run_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    fp_paths = fp_report_paths if fp_report_paths is not None else [Path(path) for path in DEFAULT_FP_REPORTS]
    positive_paths = positive_report_paths if positive_report_paths is not None else [Path(path) for path in DEFAULT_POSITIVE_REPORTS]

    for row in search_run.get("results") or []:
        if not isinstance(row, dict):
            continue
        diagnostic_path = Path(str(row.get("diagnostic_path") or ""))
        event_ts = float(row.get("event_ts") or 0.0)
        baseline_source_token_key = row.get("baseline_source_token_key")
        report = report_builder(
            diagnostic_paths=[diagnostic_path],
            fp_report_paths=fp_paths,
            positive_report_paths=positive_paths,
        )
        decision_index = report.get("decision_receipt_index") or {}
        accepted_rows = [
            item
            for item in (decision_index.get("accepted") or [])
            if isinstance(item, dict) and bool(item.get("counts_toward_accepted_total"))
        ]
        suppressed_rows = [item for item in (decision_index.get("suppressed") or []) if isinstance(item, dict)]
        uncertain_rows = [item for item in (decision_index.get("uncertain") or []) if isinstance(item, dict)]

        accepted_row = select_closest(accepted_rows, event_ts)
        stub_row = select_closest([item for item in suppressed_rows if is_output_only_stub(item)], event_ts)

        recommendation = "no_signal"
        accepted_track_id = None
        accepted_source_token_key = None
        stub_track_id = None
        if accepted_row is not None:
            accepted_track_id = int(accepted_row.get("track_id") or 0)
            accepted_source_token_key = accepted_row.get("source_token_key")
            accepted_distance = interval_distance_to_event(accepted_row, event_ts)
            if (
                accepted_source_token_key
                and accepted_source_token_key != baseline_source_token_key
                and accepted_distance <= FRESH_EVENT_SLACK_SECONDS
            ):
                recommendation = "fresh_source_lineage_candidate"
            elif stub_row is not None:
                recommendation = "shared_source_lineage_no_distinct_proof_receipt"
                stub_track_id = int(stub_row.get("track_id") or 0)
            else:
                recommendation = "restated_prior_source_lineage"
        elif stub_row is not None:
            recommendation = "output_only_stub_only"
            stub_track_id = int(stub_row.get("track_id") or 0)
        elif uncertain_rows:
            recommendation = "source_without_output_completion"

        results.append(
            {
                "event_id": str(row.get("event_id") or ""),
                "event_ts": round(event_ts, 3),
                "candidate_id": row.get("candidate_id"),
                "diagnostic_slug": row.get("diagnostic_slug"),
                "diagnostic_path": str(diagnostic_path),
                "baseline_source_token_key": baseline_source_token_key,
                "recommendation": recommendation,
                "accepted_track_id": accepted_track_id,
                "accepted_source_token_key": accepted_source_token_key,
                "stub_track_id": stub_track_id,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "search_run_path": str(search_run_path),
        "result_count": len(results),
        "results": results,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score Factory2 final-gap diagnostic searches")
    parser.add_argument("--search-run", type=Path, default=DEFAULT_SEARCH_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fp-report", action="append", dest="fp_reports", default=None)
    parser.add_argument("--positive-report", action="append", dest="positive_reports", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_final_gap_search_report(
        search_run_path=args.search_run,
        output_path=args.output,
        fp_report_paths=[Path(path) for path in args.fp_reports] if args.fp_reports else None,
        positive_report_paths=[Path(path) for path in args.positive_reports] if args.positive_reports else None,
        force=args.force,
    )
    print(json.dumps({"result_count": payload["result_count"], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
