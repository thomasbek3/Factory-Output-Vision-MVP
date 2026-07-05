#!/usr/bin/env python3
"""Reconstruct a Factory2 truth-candidate ledger from proof, runtime, and manual evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.narrow_frozen_v2.json")
DEFAULT_RUNTIME_AUDIT = Path("data/reports/factory2_runtime_event_audit.gap45.json")
DEFAULT_MANUAL_LABELS = Path("data/reports/factory2_track_labels.manual_v1.json")
DEFAULT_DIAGNOSTICS_ROOT = Path("data/diagnostics/event-windows")
DEFAULT_OUTPUT = Path("data/reports/factory2_truth_reconstruction.v0.json")
SCHEMA_VERSION = "factory2-truth-reconstruction-v0"


@dataclass(frozen=True)
class ProofConfirmedEvent:
    accepted_cluster_id: str
    diagnostic_id: str
    track_id: int
    track_key: str
    start_timestamp: float
    end_timestamp: float
    receipt_json_path: str
    receipt_card_path: str | None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def diagnostic_id_from_path(path: str) -> str:
    return Path(path).parent.name


def load_proof_confirmed_events(proof_report_path: Path) -> list[ProofConfirmedEvent]:
    payload = json.loads(proof_report_path.read_text(encoding="utf-8"))
    accepted_rows = ((payload.get("decision_receipt_index") or {}).get("accepted") or [])
    events: list[ProofConfirmedEvent] = []
    for row in accepted_rows:
        if not isinstance(row, dict) or not bool(row.get("counts_toward_accepted_total")):
            continue
        timestamps = row.get("receipt_timestamps") or {}
        diagnostic_id = diagnostic_id_from_path(str(row.get("diagnostic_path") or ""))
        track_id = int(row.get("track_id") or 0)
        events.append(
            ProofConfirmedEvent(
                accepted_cluster_id=str(row.get("accepted_cluster_id") or ""),
                diagnostic_id=diagnostic_id,
                track_id=track_id,
                track_key=f"{diagnostic_id}|{track_id}",
                start_timestamp=float(timestamps["first"]),
                end_timestamp=float(timestamps["last"]),
                receipt_json_path=str(row.get("receipt_json_path") or ""),
                receipt_card_path=str(row.get("receipt_card_path") or "") or None,
            )
        )
    events.sort(key=lambda item: (item.start_timestamp, item.end_timestamp, item.track_key))
    return events


def load_runtime_events(runtime_audit_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(runtime_audit_path.read_text(encoding="utf-8"))
    events = [item for item in (payload.get("events") or []) if isinstance(item, dict) and isinstance(item.get("event_ts"), (int, float))]
    events.sort(key=lambda item: (float(item["event_ts"]), int(item.get("track_id") or 0)))
    return events


def load_manual_track_candidates(manual_labels_path: Path, diagnostics_root: Path) -> list[dict[str, Any]]:
    payload = json.loads(manual_labels_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key, meta in payload.items():
        if not isinstance(meta, dict):
            continue
        diagnostic_id, raw_track_id = str(key).split("|", 1)
        track_id = int(raw_track_id)
        receipt_path = diagnostics_root / diagnostic_id / "track_receipts" / f"track-{track_id:06d}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        timestamps = receipt.get("timestamps") or {}
        rows.append(
            {
                "track_key": f"{diagnostic_id}|{track_id}",
                "diagnostic_id": diagnostic_id,
                "track_id": track_id,
                "start_timestamp": float(timestamps["first"]),
                "end_timestamp": float(timestamps["last"]),
                "confidence": str(meta.get("confidence") or ""),
                "crop_label": str(meta.get("crop_label") or ""),
                "short_reason": str(meta.get("short_reason") or ""),
            }
        )
    rows.sort(key=lambda item: (item["start_timestamp"], item["end_timestamp"], item["track_key"]))
    return rows


def collapse_manual_track_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    clusters: list[dict[str, Any]] = []
    current = {
        "start_timestamp": rows[0]["start_timestamp"],
        "end_timestamp": rows[0]["end_timestamp"],
        "tracks": [rows[0]],
    }
    for row in rows[1:]:
        if float(row["start_timestamp"]) <= float(current["end_timestamp"]):
            current["end_timestamp"] = max(float(current["end_timestamp"]), float(row["end_timestamp"]))
            current["tracks"].append(row)
            continue
        clusters.append(current)
        current = {
            "start_timestamp": row["start_timestamp"],
            "end_timestamp": row["end_timestamp"],
            "tracks": [row],
        }
    clusters.append(current)

    for index, cluster in enumerate(clusters, start=1):
        cluster["candidate_id"] = f"factory2-manual-candidate-{index:04d}"
        cluster["track_count"] = len(cluster["tracks"])
    return clusters


def match_proof_events_to_runtime(
    proof_events: list[ProofConfirmedEvent],
    runtime_events: list[dict[str, Any]],
    *,
    slack_seconds: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    used_runtime_indexes: set[int] = set()
    proof_rows: list[dict[str, Any]] = []
    for event in proof_events:
        best_index = None
        best_distance = float("inf")
        for index, runtime_event in enumerate(runtime_events):
            if index in used_runtime_indexes:
                continue
            event_ts = float(runtime_event["event_ts"])
            if event_ts < event.start_timestamp - slack_seconds or event_ts > event.end_timestamp + slack_seconds:
                continue
            center = (event.start_timestamp + event.end_timestamp) / 2.0
            distance = abs(event_ts - center)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        runtime_event = runtime_events[best_index] if best_index is not None else None
        if best_index is not None:
            used_runtime_indexes.add(best_index)
        proof_rows.append(
            {
                "event_id": event.accepted_cluster_id,
                "status": "proof_confirmed",
                "proof_event": asdict(event),
                "runtime_event": runtime_event,
                "counts_toward_reconstructed_total": True,
                "needs_human_confirmation": False,
            }
        )
    remaining_runtime = [event for index, event in enumerate(runtime_events) if index not in used_runtime_indexes]
    return proof_rows, remaining_runtime


def build_truth_reconstruction(
    *,
    proof_report_path: Path,
    runtime_audit_path: Path,
    manual_labels_path: Path,
    diagnostics_root: Path,
    output_path: Path,
    runtime_match_slack_seconds: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    proof_events = load_proof_confirmed_events(proof_report_path)
    runtime_events = load_runtime_events(runtime_audit_path)
    manual_rows = load_manual_track_candidates(manual_labels_path, diagnostics_root)
    proof_rows, runtime_only = match_proof_events_to_runtime(
        proof_events,
        runtime_events,
        slack_seconds=runtime_match_slack_seconds,
    )

    proof_track_keys = {event.track_key for event in proof_events}
    manual_only_clusters = collapse_manual_track_candidates(
        [row for row in manual_rows if row["track_key"] not in proof_track_keys]
    )

    events: list[dict[str, Any]] = list(proof_rows)
    for index, runtime_event in enumerate(runtime_only, start=1):
        events.append(
            {
                "event_id": f"factory2-runtime-only-{index:04d}",
                "status": "runtime_only_needs_receipt_match",
                "runtime_event": runtime_event,
                "counts_toward_reconstructed_total": False,
                "needs_human_confirmation": True,
            }
        )
    for cluster in manual_only_clusters:
        events.append(
            {
                "event_id": cluster["candidate_id"],
                "status": "manual_crop_visible_needs_source_output_chain",
                "start_timestamp": round(float(cluster["start_timestamp"]), 3),
                "end_timestamp": round(float(cluster["end_timestamp"]), 3),
                "track_count": int(cluster["track_count"]),
                "tracks": cluster["tracks"],
                "counts_toward_reconstructed_total": False,
                "needs_human_confirmation": True,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "proof_report_path": str(proof_report_path),
        "runtime_audit_path": str(runtime_audit_path),
        "manual_labels_path": str(manual_labels_path),
        "diagnostics_root": str(diagnostics_root),
        "target_human_count": 23,
        "is_authoritative_human_truth": False,
        "proof_confirmed_count": len(proof_rows),
        "runtime_only_count": len(runtime_only),
        "manual_only_candidate_count": len(manual_only_clusters),
        "runtime_match_slack_seconds": runtime_match_slack_seconds,
        "events": events,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct a Factory2 truth-candidate ledger")
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--runtime-audit", type=Path, default=DEFAULT_RUNTIME_AUDIT)
    parser.add_argument("--manual-labels", type=Path, default=DEFAULT_MANUAL_LABELS)
    parser.add_argument("--diagnostics-root", type=Path, default=DEFAULT_DIAGNOSTICS_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-match-slack-seconds", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_truth_reconstruction(
        proof_report_path=args.proof_report,
        runtime_audit_path=args.runtime_audit,
        manual_labels_path=args.manual_labels,
        diagnostics_root=args.diagnostics_root,
        output_path=args.output,
        runtime_match_slack_seconds=args.runtime_match_slack_seconds,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "proof_confirmed_count": payload["proof_confirmed_count"],
                "runtime_only_count": payload["runtime_only_count"],
                "manual_only_candidate_count": payload["manual_only_candidate_count"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
