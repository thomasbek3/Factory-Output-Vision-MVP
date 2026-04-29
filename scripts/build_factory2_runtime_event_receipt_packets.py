#!/usr/bin/env python3
"""Build runtime-event-centered proof receipt packets for unresolved Factory2 events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_morning_proof_report import (
    load_receipt_payload,
    source_lineage_receipt_paths,
    source_lineage_track_ids,
    source_token_key,
)

DEFAULT_RECONSTRUCTION = Path("data/reports/factory2_truth_reconstruction.gap45_recentdedupe.v0.json")
DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_runtime_event_receipt_packets.gap45_recentdedupe.v1.json")
SCHEMA_VERSION = "factory2-runtime-event-receipt-packets-v1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def row_window(row: dict[str, Any]) -> tuple[float, float] | None:
    window = row.get("window") or {}
    try:
        return float(window.get("start_timestamp")), float(window.get("end_timestamp"))
    except (TypeError, ValueError):
        return None


def summarize_receipt(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "diagnostic_path": row.get("diagnostic_path"),
        "track_id": int(row.get("track_id") or 0),
        "decision": row.get("decision"),
        "reason": row.get("reason"),
        "failure_link": row.get("failure_link"),
        "source_token_key": row.get("source_token_key"),
        "source_lineage_track_ids": [int(item) for item in (row.get("source_lineage_track_ids") or [])],
        "receipt_timestamps": row.get("receipt_timestamps") or {},
        "receipt_json_path": row.get("receipt_json_path"),
        "receipt_card_path": row.get("receipt_card_path"),
        "raw_crop_paths": row.get("raw_crop_paths") or [],
    }


def hydrate_source_lineage(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("source_token_key"):
        return row
    receipt_path = row.get("receipt_json_path")
    receipt_payload = load_receipt_payload(str(receipt_path) if receipt_path else None)
    gate_row = receipt_payload.get("perception_gate") or {}
    if not isinstance(gate_row, dict):
        return row
    track_id = row.get("track_id")
    hydrated = dict(row)
    hydrated["source_lineage_track_ids"] = source_lineage_track_ids(track_id=track_id, row=gate_row)
    hydrated["source_lineage_receipt_paths"] = source_lineage_receipt_paths(receipt_path=str(receipt_path) if receipt_path else None, row=gate_row)
    hydrated["source_token_key"] = source_token_key(
        track_id=track_id,
        receipt_path=str(receipt_path) if receipt_path else None,
        row=gate_row,
    )
    return hydrated


def covering_rows(rows: list[dict[str, Any]], event_ts: float) -> list[dict[str, Any]]:
    covered: list[dict[str, Any]] = []
    for row in rows:
        window = row_window(row)
        if window is None:
            continue
        if window[0] <= event_ts <= window[1]:
            covered.append(row)
    return covered


def nearest_prior_accepted_receipt(rows: list[dict[str, Any]], event_ts: float) -> dict[str, Any] | None:
    accepted = [row for row in rows if str(row.get("decision") or "") == "allow_source_token"]
    candidates: list[tuple[float, float, dict[str, Any]]] = []
    for row in accepted:
        interval = receipt_interval(row)
        if interval is None:
            continue
        if interval[1] > event_ts:
            continue
        candidates.append((event_ts - interval[1], interval[0], row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2].get("diagnostic_path") or ""), int(item[2].get("track_id") or 0)))
    return candidates[0][2]


def nearest_output_only_stub_receipt(rows: list[dict[str, Any]], event_ts: float, slack_seconds: float) -> dict[str, Any] | None:
    candidates: list[tuple[float, float, dict[str, Any]]] = []
    for row in rows:
        failure_link = str(row.get("failure_link") or "")
        reason = str(row.get("reason") or "")
        if failure_link != "static_stack_or_resident_output" and reason not in {"static_stack_edge", "output_only_no_source_token"}:
            continue
        interval = receipt_interval(row)
        if interval is None:
            continue
        center = (interval[0] + interval[1]) / 2.0
        distance = abs(center - event_ts)
        if distance > slack_seconds:
            continue
        candidates.append((distance, interval[0], row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2].get("diagnostic_path") or ""), int(item[2].get("track_id") or 0)))
    return candidates[0][2]


def build_packet_for_runtime_event(
    *,
    row: dict[str, Any],
    decision_rows: list[dict[str, Any]],
    packet_slack_seconds: float,
) -> dict[str, Any]:
    runtime_event = row.get("runtime_event") or {}
    event_ts = float(runtime_event.get("event_ts") or 0.0)
    covered_rows = covering_rows(decision_rows, event_ts)
    covered_rows.sort(
        key=lambda item: (
            abs(((receipt_interval(item) or (event_ts, event_ts))[0] + (receipt_interval(item) or (event_ts, event_ts))[1]) / 2.0 - event_ts),
            str(item.get("diagnostic_path") or ""),
            int(item.get("track_id") or 0),
        )
    )
    prior_accepted = nearest_prior_accepted_receipt(covered_rows, event_ts)
    output_stub = nearest_output_only_stub_receipt(covered_rows, event_ts, packet_slack_seconds)

    reason_strings: list[str] = []
    recommendation = "unresolved_runtime_proof_divergence"
    shared_source_lineage_risk = False
    if not covered_rows:
        recommendation = "build_new_diagnostic"
        reason_strings.append("No current proof receipt or diagnostic window covers this runtime event.")
    elif prior_accepted is not None and output_stub is not None:
        recommendation = "shared_source_lineage_no_distinct_proof_receipt"
        shared_source_lineage_risk = bool(prior_accepted.get("source_token_key"))
        reason_strings.append(
            "Covering proof receipts show an earlier accepted carry plus a later output-only stub, not a distinct new source-backed receipt."
        )
    elif prior_accepted is not None:
        reason_strings.append("A prior accepted proof receipt exists in the covering window, but no nearby output-only stub explains the runtime event.")
    else:
        reason_strings.append("Covering receipts exist, but none currently provide a prior accepted proof source lineage.")

    return {
        "event_id": str(row.get("event_id") or ""),
        "event_ts": round(event_ts, 3),
        "runtime_track_id": int(runtime_event.get("track_id") or 0),
        "runtime_count_total": int(runtime_event.get("count_total") or 0),
        "runtime_reason": str(runtime_event.get("reason") or ""),
        "covering_receipt_count": len(covered_rows),
        "covering_diagnostic_paths": sorted({str(item.get("diagnostic_path") or "") for item in covered_rows if item.get("diagnostic_path")}),
        "nearby_receipts": [summarize_receipt(item) for item in covered_rows[:6]],
        "prior_accepted_receipt": summarize_receipt(prior_accepted),
        "nearest_output_only_stub_receipt": summarize_receipt(output_stub),
        "shared_source_lineage_risk": shared_source_lineage_risk,
        "recommendation": recommendation,
        "reason_strings": reason_strings,
    }


def build_runtime_event_receipt_packets(
    *,
    reconstruction_path: Path,
    proof_report_path: Path,
    output_path: Path,
    packet_slack_seconds: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if packet_slack_seconds < 0:
        raise ValueError("packet_slack_seconds must be non-negative")

    reconstruction = load_json(reconstruction_path)
    proof_report = load_json(proof_report_path)
    decision_index = proof_report.get("decision_receipt_index") or {}
    decision_rows = []
    for bucket in ("accepted", "suppressed", "uncertain"):
        for item in decision_index.get(bucket) or []:
            if isinstance(item, dict):
                decision_rows.append(hydrate_source_lineage(item))

    runtime_only_rows = [
        row
        for row in (reconstruction.get("events") or [])
        if isinstance(row, dict) and row.get("status") == "runtime_only_needs_receipt_match"
    ]
    packets = [
        build_packet_for_runtime_event(
            row=row,
            decision_rows=decision_rows,
            packet_slack_seconds=packet_slack_seconds,
        )
        for row in runtime_only_rows
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "reconstruction_path": str(reconstruction_path),
        "proof_report_path": str(proof_report_path),
        "packet_slack_seconds": packet_slack_seconds,
        "runtime_only_event_count": len(runtime_only_rows),
        "packet_count": len(packets),
        "packets": packets,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build runtime-event-centered Factory2 proof receipt packets")
    parser.add_argument("--reconstruction", type=Path, default=DEFAULT_RECONSTRUCTION)
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--packet-slack-seconds", type=float, default=2.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_runtime_event_receipt_packets(
        reconstruction_path=args.reconstruction,
        proof_report_path=args.proof_report,
        output_path=args.output,
        packet_slack_seconds=args.packet_slack_seconds,
        force=args.force,
    )
    print(json.dumps({"packet_count": payload["packet_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
