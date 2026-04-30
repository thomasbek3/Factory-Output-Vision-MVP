#!/usr/bin/env python3
"""Compare an observed app run event list against the factory2 truth ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "factory2-app-run-vs-truth-comparison-v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sort_events(events: list[dict[str, Any]], *, timestamp_key: str) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: (float(item.get(timestamp_key) or 0.0), int(item.get("count_total") or item.get("runtime_total_after_event") or 0)))


def _pending_truth_event(truth_event: dict[str, Any], *, coverage_end_sec: float | None) -> dict[str, Any]:
    return {
        "truth_event_id": truth_event.get("truth_event_id"),
        "event_ts": float(truth_event.get("event_ts") or 0.0),
        "observed_coverage_end_sec": None if coverage_end_sec is None else round(float(coverage_end_sec), 3),
    }


def compare_app_run_to_truth_ledger(
    *,
    truth_ledger_path: Path,
    observed_events_path: Path,
    output_path: Path,
    tolerance_sec: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    truth_payload = _read_json(truth_ledger_path)
    observed_payload = _read_json(observed_events_path)
    truth_events = _sort_events(list(truth_payload.get("events") or []), timestamp_key="event_ts")
    observed_events = _sort_events(list(observed_payload.get("events") or []), timestamp_key="event_ts")
    observed_coverage_end_sec = observed_payload.get("observed_coverage_end_sec")
    if observed_coverage_end_sec is None and observed_events:
        observed_coverage_end_sec = max(float(item.get("event_ts") or 0.0) for item in observed_events)
    observed_run_complete = bool(observed_payload.get("run_complete"))

    truth_index = 0
    observed_index = 0
    matched: list[dict[str, Any]] = []
    missing_truth: list[dict[str, Any]] = []
    pending_truth: list[dict[str, Any]] = []
    unexpected_observed: list[dict[str, Any]] = []
    first_divergence: dict[str, Any] | None = None

    while truth_index < len(truth_events) and observed_index < len(observed_events):
        truth_event = truth_events[truth_index]
        observed_event = observed_events[observed_index]
        truth_ts = float(truth_event.get("event_ts") or 0.0)
        observed_ts = float(observed_event.get("event_ts") or 0.0)
        delta = observed_ts - truth_ts
        if abs(delta) <= tolerance_sec:
            matched.append(
                {
                    "truth_event_id": truth_event.get("truth_event_id"),
                    "truth_event_ts": truth_ts,
                    "observed_event_ts": observed_ts,
                    "delta_sec": round(delta, 3),
                    "observed_track_id": observed_event.get("track_id"),
                }
            )
            truth_index += 1
            observed_index += 1
            continue
        if observed_ts < truth_ts:
            unexpected = {
                "event_ts": observed_ts,
                "track_id": observed_event.get("track_id"),
                "runtime_total_after_event": observed_event.get("runtime_total_after_event"),
            }
            unexpected_observed.append(unexpected)
            if first_divergence is None:
                first_divergence = {"type": "unexpected_observed", **unexpected}
            observed_index += 1
            continue
        missing = {
            "truth_event_id": truth_event.get("truth_event_id"),
            "event_ts": truth_ts,
        }
        missing_truth.append(missing)
        if first_divergence is None:
            first_divergence = {"type": "missing_truth", **missing}
        truth_index += 1

    while truth_index < len(truth_events):
        truth_event = truth_events[truth_index]
        truth_ts = float(truth_event.get("event_ts") or 0.0)
        if (not observed_run_complete) and observed_coverage_end_sec is not None and truth_ts > float(observed_coverage_end_sec) + float(tolerance_sec):
            pending = _pending_truth_event(truth_event, coverage_end_sec=float(observed_coverage_end_sec))
            pending_truth.append(pending)
            if first_divergence is None:
                first_divergence = {"type": "incomplete_coverage", **pending}
            truth_index += 1
            continue
        missing = {
            "truth_event_id": truth_event.get("truth_event_id"),
            "event_ts": truth_ts,
        }
        missing_truth.append(missing)
        if first_divergence is None:
            first_divergence = {"type": "missing_truth", **missing}
        truth_index += 1

    while observed_index < len(observed_events):
        observed_event = observed_events[observed_index]
        unexpected = {
            "event_ts": float(observed_event.get("event_ts") or 0.0),
            "track_id": observed_event.get("track_id"),
            "runtime_total_after_event": observed_event.get("runtime_total_after_event"),
        }
        unexpected_observed.append(unexpected)
        if first_divergence is None:
            first_divergence = {"type": "unexpected_observed", **unexpected}
        observed_index += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "truth_ledger_path": str(truth_ledger_path),
        "observed_events_path": str(observed_events_path),
        "tolerance_sec": float(tolerance_sec),
        "truth_event_count": len(truth_events),
        "observed_event_count": len(observed_events),
        "observed_run_complete": observed_run_complete,
        "observed_coverage_end_sec": observed_coverage_end_sec,
        "matched_count": len(matched),
        "missing_truth_count": len(missing_truth),
        "pending_truth_count": len(pending_truth),
        "unexpected_observed_count": len(unexpected_observed),
        "first_divergence": first_divergence,
        "matched": matched,
        "missing_truth": missing_truth,
        "pending_truth": pending_truth,
        "unexpected_observed": unexpected_observed,
    }
    _write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a live app run event list against the factory2 truth ledger")
    parser.add_argument("--truth-ledger", type=Path, required=True)
    parser.add_argument("--observed-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tolerance-sec", type=float, default=0.5)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = compare_app_run_to_truth_ledger(
        truth_ledger_path=args.truth_ledger,
        observed_events_path=args.observed_events,
        output_path=args.output,
        tolerance_sec=args.tolerance_sec,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "matched_count": payload["matched_count"],
                "missing_truth_count": payload["missing_truth_count"],
                "pending_truth_count": payload["pending_truth_count"],
                "unexpected_observed_count": payload["unexpected_observed_count"],
                "first_divergence": payload["first_divergence"],
            }
        )
    )


if __name__ == "__main__":
    main()
