#!/usr/bin/env python3
"""Build a targeted diagnostic search plan for Factory2's unresolved proof gaps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_PACKETS = Path("data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_final_gap_search_plan.v1.json")
DEFAULT_LEAD_SECONDS = [4.0, 6.0, 8.0, 10.0, 12.0]
DEFAULT_TAIL_SECONDS = [2.0, 3.0, 4.0, 6.0]
DEFAULT_FPS_VALUES = [5.0, 8.0, 10.0]
SCHEMA_VERSION = "factory2-final-gap-search-plan-v1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def candidate_id(*, event_id: str, lead_seconds: float, tail_seconds: float, fps: float) -> str:
    suffix = event_id.split("-")[-1]
    return f"{suffix}-lead{int(round(lead_seconds * 10)):03d}-tail{int(round(tail_seconds * 10)):03d}-fps{int(round(fps * 10)):03d}"


def build_final_gap_search_plan(
    *,
    packets_path: Path,
    output_path: Path,
    lead_seconds: list[float],
    tail_seconds: list[float],
    fps_values: list[float],
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if not lead_seconds or not tail_seconds or not fps_values:
        raise ValueError("lead_seconds, tail_seconds, and fps_values must all be non-empty")

    payload = json.loads(packets_path.read_text(encoding="utf-8"))
    packets = payload.get("packets") or []
    targets: list[dict[str, Any]] = []
    total_candidates = 0

    for packet in packets:
        if not isinstance(packet, dict):
            continue
        if str(packet.get("recommendation") or "") != "shared_source_lineage_no_distinct_proof_receipt":
            continue

        event_id = str(packet.get("event_id") or "")
        event_ts = float(packet.get("event_ts") or 0.0)
        prior_accepted = packet.get("prior_accepted_receipt") or {}
        candidates: list[dict[str, Any]] = []
        for lead in sorted(float(value) for value in lead_seconds):
            for tail in sorted(float(value) for value in tail_seconds):
                for fps in sorted(float(value) for value in fps_values):
                    start_seconds = round(max(0.0, event_ts - lead), 3)
                    end_seconds = round(event_ts + tail, 3)
                    candidates.append(
                        {
                            "candidate_id": candidate_id(
                                event_id=event_id,
                                lead_seconds=lead,
                                tail_seconds=tail,
                                fps=fps,
                            ),
                            "event_id": event_id,
                            "event_ts": round(event_ts, 3),
                            "start_seconds": start_seconds,
                            "end_seconds": end_seconds,
                            "fps": fps,
                            "lead_seconds": lead,
                            "tail_seconds": tail,
                            "duration_seconds": round(end_seconds - start_seconds, 3),
                        }
                    )
        total_candidates += len(candidates)
        targets.append(
            {
                "event_id": event_id,
                "event_ts": round(event_ts, 3),
                "covering_diagnostic_paths": [str(path) for path in (packet.get("covering_diagnostic_paths") or [])],
                "baseline_source_token_key": prior_accepted.get("source_token_key"),
                "baseline_receipt_timestamps": prior_accepted.get("receipt_timestamps") or {},
                "candidates": candidates,
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "packets_path": str(packets_path),
        "event_count": len(targets),
        "candidate_count": total_candidates,
        "lead_seconds": sorted(float(value) for value in lead_seconds),
        "tail_seconds": sorted(float(value) for value in tail_seconds),
        "fps_values": sorted(float(value) for value in fps_values),
        "targets": targets,
    }
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a targeted Factory2 final-gap diagnostic search plan")
    parser.add_argument("--packets", type=Path, default=DEFAULT_PACKETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lead-seconds", type=float, action="append", dest="lead_seconds", default=None)
    parser.add_argument("--tail-seconds", type=float, action="append", dest="tail_seconds", default=None)
    parser.add_argument("--fps", type=float, action="append", dest="fps_values", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_final_gap_search_plan(
        packets_path=args.packets,
        output_path=args.output,
        lead_seconds=args.lead_seconds or list(DEFAULT_LEAD_SECONDS),
        tail_seconds=args.tail_seconds or list(DEFAULT_TAIL_SECONDS),
        fps_values=args.fps_values or list(DEFAULT_FPS_VALUES),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "event_count": payload["event_count"],
                "candidate_count": payload["candidate_count"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
