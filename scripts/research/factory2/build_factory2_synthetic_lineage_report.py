#!/usr/bin/env python3
"""Summarize Factory2 approved-delivery-chain lineage provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_RUNTIME_AUDIT = Path("data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json")
DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json")
DEFAULT_DIVERGENCE = Path("data/reports/factory2_proof_runtime_divergence.final_two_v2.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json")
SCHEMA_VERSION = "factory2-synthetic-lineage-report-v1"
PROOF_OVERLAP_TOLERANCE_SECONDS = 1.0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _last_timestamp(rows: list[dict[str, Any]]) -> float | None:
    timestamps = [float(row["timestamp"]) for row in rows if "timestamp" in row]
    if not timestamps:
        return None
    return max(timestamps)


def _first_timestamp(rows: list[dict[str, Any]]) -> float | None:
    timestamps = [float(row["timestamp"]) for row in rows if "timestamp" in row]
    if not timestamps:
        return None
    return min(timestamps)


def _source_gap_seconds(event: dict[str, Any], track_histories: dict[str, list[dict[str, Any]]]) -> float | None:
    source_track_id = event.get("source_track_id")
    if source_track_id is None:
        return None
    source_history = track_histories.get(str(source_track_id)) or []
    last_source_ts = _last_timestamp(source_history)
    if last_source_ts is None:
        return None
    return round(float(event["event_ts"]) - last_source_ts, 3)


def _observation_count(track_id: int | None, track_histories: dict[str, list[dict[str, Any]]]) -> int:
    if track_id is None:
        return 0
    return len(track_histories.get(str(track_id)) or [])


def _accepted_intervals(proof: dict[str, Any]) -> list[tuple[float, float]]:
    accepted = ((proof.get("decision_receipt_index") or {}).get("accepted") or [])
    intervals: list[tuple[float, float]] = []
    for row in accepted:
        if not isinstance(row, dict) or not row.get("counts_toward_accepted_total"):
            continue
        receipt_timestamps = row.get("receipt_timestamps") or {}
        first = receipt_timestamps.get("first")
        last = receipt_timestamps.get("last")
        if first is None or last is None:
            continue
        intervals.append((float(first), float(last)))
    return intervals


def build_synthetic_lineage_report(
    *,
    runtime_audit_path: Path,
    proof_report_path: Path,
    divergence_path: Path,
    output_path: Path,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    runtime = json.loads(runtime_audit_path.read_text(encoding="utf-8"))
    proof = json.loads(proof_report_path.read_text(encoding="utf-8"))
    divergence = json.loads(divergence_path.read_text(encoding="utf-8"))

    track_histories = runtime.get("track_histories") or {}
    proof_intervals = _accepted_intervals(proof)
    divergent_timestamps = {
        round(float(row["event_ts"]), 3)
        for row in (divergence.get("divergent_events") or [])
        if isinstance(row, dict) and row.get("event_ts") is not None
    }

    approved_delivery_chain_events = [
        row
        for row in (runtime.get("events") or [])
        if isinstance(row, dict) and row.get("reason") == "approved_delivery_chain"
    ]
    synthetic_events: list[dict[str, Any]] = []
    inherited_events: list[dict[str, Any]] = []
    for row in approved_delivery_chain_events:
        enriched = dict(row)
        source_track_id = row.get("source_track_id")
        source_history = track_histories.get(str(source_track_id)) or []
        enriched["is_divergent"] = round(float(row["event_ts"]), 3) in divergent_timestamps
        enriched["source_gap_seconds"] = _source_gap_seconds(row, track_histories)
        enriched["source_track_observation_count"] = _observation_count(source_track_id, track_histories)
        enriched["output_track_observation_count"] = _observation_count(row.get("track_id"), track_histories)
        event_ts = float(row["event_ts"])
        enriched["has_overlapping_proof_receipt"] = any(
            (start - PROOF_OVERLAP_TOLERANCE_SECONDS) <= event_ts <= (end + PROOF_OVERLAP_TOLERANCE_SECONDS)
            for start, end in proof_intervals
        )
        first_source_ts = _first_timestamp(source_history)
        enriched["recommended_search_start_seconds"] = (
            round(max(0.0, first_source_ts - 1.0), 3) if first_source_ts is not None else None
        )
        enriched["recommended_search_end_seconds"] = round(event_ts + 2.0, 3)
        if row.get("provenance_status") == "synthetic_approved_chain_token":
            synthetic_events.append(enriched)
        else:
            inherited_events.append(enriched)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "runtime_audit_path": str(runtime_audit_path),
        "proof_report_path": str(proof_report_path),
        "divergence_path": str(divergence_path),
        "proof_accepted_count": int(proof.get("accepted_count") or 0),
        "approved_delivery_chain_count": len(approved_delivery_chain_events),
        "synthetic_count": len(synthetic_events),
        "inherited_live_count": len(inherited_events),
        "divergent_synthetic_count": sum(1 for row in synthetic_events if row["is_divergent"]),
        "synthetic_with_overlapping_proof_count": sum(
            1 for row in synthetic_events if row["has_overlapping_proof_receipt"]
        ),
        "synthetic_without_overlapping_proof_count": sum(
            1 for row in synthetic_events if not row["has_overlapping_proof_receipt"]
        ),
        "synthetic_without_overlapping_proof_event_timestamps": [
            round(float(row["event_ts"]), 3)
            for row in synthetic_events
            if not row["has_overlapping_proof_receipt"]
        ],
        "synthetic_events": synthetic_events,
        "inherited_events": inherited_events,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Factory2 synthetic lineage provenance report")
    parser.add_argument("--runtime-audit", type=Path, default=DEFAULT_RUNTIME_AUDIT)
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--divergence", type=Path, default=DEFAULT_DIVERGENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_synthetic_lineage_report(
        runtime_audit_path=args.runtime_audit,
        proof_report_path=args.proof_report,
        divergence_path=args.divergence,
        output_path=args.output,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "approved_delivery_chain_count": payload["approved_delivery_chain_count"],
                "synthetic_count": payload["synthetic_count"],
                "inherited_live_count": payload["inherited_live_count"],
                "divergent_synthetic_count": payload["divergent_synthetic_count"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
