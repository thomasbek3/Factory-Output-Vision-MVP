#!/usr/bin/env python3
"""Build a runtime-backed proof-alignment queue for Factory2."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.build_morning_proof_report import DEFAULT_DIAGNOSTICS

DEFAULT_RECONSTRUCTION = Path("data/reports/factory2_truth_reconstruction.gap45_recentdedupe.v0.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json")
DEFAULT_EVENT_WINDOWS_ROOT = Path("data/diagnostics/event-windows")
SCHEMA_VERSION = "factory2-proof-alignment-queue-v1"


@dataclass(frozen=True)
class DiagnosticWindow:
    path: Path
    start_timestamp: float
    end_timestamp: float

    @property
    def duration(self) -> float:
        return self.end_timestamp - self.start_timestamp

    @property
    def center_timestamp(self) -> float:
        return (self.start_timestamp + self.end_timestamp) / 2.0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_diagnostic_window(path: Path) -> DiagnosticWindow | None:
    payload = load_json(path)
    window = payload.get("window") or payload
    try:
        start_timestamp = float(window["start_timestamp"])
        end_timestamp = float(window["end_timestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    return DiagnosticWindow(path=path, start_timestamp=start_timestamp, end_timestamp=end_timestamp)


def discover_candidate_diagnostic_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*/diagnostic.json"))


def select_preferred_diagnostic(event_ts: float, windows: list[DiagnosticWindow]) -> DiagnosticWindow | None:
    if not windows:
        return None
    return min(
        windows,
        key=lambda window: (
            window.duration,
            abs(window.center_timestamp - event_ts),
            str(window.path),
        ),
    )


def build_proof_alignment_queue(
    *,
    reconstruction_path: Path,
    output_path: Path,
    active_proof_diagnostic_paths: list[Path],
    candidate_diagnostic_paths: list[Path],
    padding_seconds: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if padding_seconds < 0:
        raise ValueError("padding_seconds must be non-negative")

    reconstruction = load_json(reconstruction_path)
    active_windows = [window for path in active_proof_diagnostic_paths if (window := load_diagnostic_window(path)) is not None]
    candidate_windows = [window for path in candidate_diagnostic_paths if (window := load_diagnostic_window(path)) is not None]

    runtime_only_rows = [
        row
        for row in (reconstruction.get("events") or [])
        if isinstance(row, dict) and row.get("status") == "runtime_only_needs_receipt_match"
    ]
    queue: list[dict[str, Any]] = []
    for row in runtime_only_rows:
        runtime_event = row.get("runtime_event") or {}
        event_ts = float(runtime_event["event_ts"])
        covering_active = [
            window for window in active_windows
            if window.start_timestamp <= event_ts <= window.end_timestamp
        ]
        covering_candidates = [
            window for window in candidate_windows
            if window.start_timestamp <= event_ts <= window.end_timestamp
        ]
        preferred = select_preferred_diagnostic(event_ts, covering_candidates)
        queue.append(
            {
                "event_id": str(row.get("event_id") or ""),
                "runtime_track_id": int(runtime_event.get("track_id") or 0),
                "runtime_count_total": int(runtime_event.get("count_total") or 0),
                "event_ts": round(event_ts, 3),
                "covered_by_active_proof": bool(covering_active),
                "active_proof_diagnostic_paths": [str(window.path) for window in covering_active],
                "covering_existing_diagnostic_paths": [str(window.path) for window in covering_candidates],
                "preferred_diagnostic_path": str(preferred.path) if preferred is not None else None,
                "preferred_diagnostic_window": None
                if preferred is None
                else {
                    "start_timestamp": round(preferred.start_timestamp, 3),
                    "end_timestamp": round(preferred.end_timestamp, 3),
                },
                "suggested_action": "inspect_existing_diagnostic" if preferred is not None else "build_new_diagnostic",
                "suggested_start_seconds": round(max(0.0, event_ts - padding_seconds), 3),
                "suggested_end_seconds": round(event_ts + padding_seconds, 3),
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "reconstruction_path": str(reconstruction_path),
        "runtime_only_count": len(runtime_only_rows),
        "queue_count": len(queue),
        "active_proof_diagnostic_paths": [str(path) for path in active_proof_diagnostic_paths],
        "candidate_diagnostic_paths": [str(path) for path in candidate_diagnostic_paths],
        "padding_seconds": padding_seconds,
        "queue": queue,
    }
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Factory2 runtime-backed proof alignment queue")
    parser.add_argument("--reconstruction", type=Path, default=DEFAULT_RECONSTRUCTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--event-windows-root", type=Path, default=DEFAULT_EVENT_WINDOWS_ROOT)
    parser.add_argument("--padding-seconds", type=float, default=20.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_proof_alignment_queue(
        reconstruction_path=args.reconstruction,
        output_path=args.output,
        active_proof_diagnostic_paths=[Path(path) for path in DEFAULT_DIAGNOSTICS],
        candidate_diagnostic_paths=discover_candidate_diagnostic_paths(args.event_windows_root),
        padding_seconds=args.padding_seconds,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "runtime_only_count": payload["runtime_only_count"],
                "queue_count": payload["queue_count"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
