#!/usr/bin/env python3
"""Build a single factory2 human-truth ledger from runtime/proof artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "factory2-human-truth-ledger-v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _event_sort_key(event: dict[str, Any]) -> tuple[float, int]:
    return (float(event.get("event_ts") or 0.0), int(event.get("count_total") or 0))


def _match_reconstruction_event(
    runtime_event: dict[str, Any],
    reconstruction_events: list[dict[str, Any]],
    used_indexes: set[int],
    *,
    tolerance_sec: float,
) -> dict[str, Any] | None:
    best_index: int | None = None
    best_distance: float | None = None
    runtime_ts = float(runtime_event.get("event_ts") or 0.0)
    for index, candidate in enumerate(reconstruction_events):
        if index in used_indexes:
            continue
        candidate_runtime = candidate.get("runtime_event") or {}
        candidate_ts = float(candidate_runtime.get("event_ts") or 0.0)
        distance = abs(runtime_ts - candidate_ts)
        if distance > tolerance_sec:
            continue
        if best_distance is None or distance < best_distance:
            best_index = index
            best_distance = distance
    if best_index is None:
        return None
    used_indexes.add(best_index)
    return reconstruction_events[best_index]


def build_human_truth_ledger(
    *,
    runtime_audit_path: Path,
    reconstruction_path: Path | None,
    authority_ledger_path: Path | None,
    output_path: Path,
    expected_human_total: int,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    runtime_audit = _read_json(runtime_audit_path)
    reconstruction = _read_json(reconstruction_path) if reconstruction_path is not None else {"events": []}
    authority_ledger = _read_json(authority_ledger_path) if authority_ledger_path is not None else {}

    runtime_events = sorted(list(runtime_audit.get("events") or []), key=_event_sort_key)
    reconstruction_events = list(reconstruction.get("events") or [])
    unresolved_synthetic_ts = {
        round(float(ts), 3) for ts in authority_ledger.get("synthetic_without_distinct_proof_event_timestamps") or []
    }

    used_reconstruction_indexes: set[int] = set()
    ledger_events: list[dict[str, Any]] = []
    matched_proof_confirmed_count = 0
    needs_manual_confirmation_count = 0

    for index, runtime_event in enumerate(runtime_events, start=1):
        matched = _match_reconstruction_event(
            runtime_event,
            reconstruction_events,
            used_reconstruction_indexes,
            tolerance_sec=0.05,
        )
        authority_hint = None
        rounded_ts = round(float(runtime_event.get("event_ts") or 0.0), 3)
        if rounded_ts in unresolved_synthetic_ts:
            authority_hint = "synthetic_without_distinct_proof"
        elif runtime_event.get("count_authority") == "runtime_inferred_only":
            authority_hint = "runtime_inferred_only"

        proof_status = "runtime_only"
        proof_track_key = None
        proof_diagnostic_id = None
        if matched is not None and matched.get("status") == "proof_confirmed":
            proof_status = "proof_confirmed"
            proof = matched.get("proof_event") or {}
            proof_track_key = proof.get("track_key")
            proof_diagnostic_id = proof.get("diagnostic_id")
            matched_proof_confirmed_count += 1

        needs_manual_confirmation = authority_hint is not None or proof_status != "proof_confirmed"
        if needs_manual_confirmation:
            needs_manual_confirmation_count += 1

        ledger_events.append(
            {
                "truth_event_id": f"factory2-truth-{index:04d}",
                "event_ts": rounded_ts,
                "count_total": int(runtime_event.get("count_total") or index),
                "runtime_track_id": runtime_event.get("track_id"),
                "runtime_reason": runtime_event.get("reason"),
                "count_authority": runtime_event.get("count_authority"),
                "provenance_status": runtime_event.get("provenance_status"),
                "proof_status": proof_status,
                "proof_track_key": proof_track_key,
                "proof_diagnostic_id": proof_diagnostic_id,
                "authority_hint": authority_hint,
                "needs_manual_confirmation": needs_manual_confirmation,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "runtime_audit_path": str(runtime_audit_path),
        "reconstruction_path": None if reconstruction_path is None else str(reconstruction_path),
        "authority_ledger_path": None if authority_ledger_path is None else str(authority_ledger_path),
        "expected_human_total": int(expected_human_total),
        "runtime_event_count": len(runtime_events),
        "matched_proof_confirmed_count": matched_proof_confirmed_count,
        "needs_manual_confirmation_count": needs_manual_confirmation_count,
        "events": ledger_events,
    }
    _write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single factory2 human-truth ledger from runtime/proof artifacts")
    parser.add_argument("--runtime-audit", type=Path, required=True)
    parser.add_argument("--reconstruction", type=Path)
    parser.add_argument("--authority-ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-human-total", type=int, default=23)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_human_truth_ledger(
        runtime_audit_path=args.runtime_audit,
        reconstruction_path=args.reconstruction,
        authority_ledger_path=args.authority_ledger,
        output_path=args.output,
        expected_human_total=args.expected_human_total,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "runtime_event_count": payload["runtime_event_count"],
                "expected_human_total": payload["expected_human_total"],
                "needs_manual_confirmation_count": payload["needs_manual_confirmation_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
