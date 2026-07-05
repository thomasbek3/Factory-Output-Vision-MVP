#!/usr/bin/env python3
"""Compare one-pass Factory2 runtime events against the manual truth ledger."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_LABELS_PATH = Path("data/reports/factory2_track_labels.manual_v1.json")
DEFAULT_RUNTIME_AUDIT_PATH = Path("data/reports/factory2_runtime_event_audit.full.json")
DEFAULT_OUTPUT_PATH = Path("data/reports/factory2_runtime_truth_gap.full.json")
DEFAULT_DIAGNOSTICS_ROOT = Path("data/diagnostics/event-windows")
SCHEMA_VERSION = "factory2-runtime-truth-gap-v1"


@dataclass(frozen=True)
class ReviewedTrack:
    diagnostic_id: str
    track_id: int
    start_timestamp: float
    end_timestamp: float
    crop_label: str
    confidence: str
    short_reason: str


@dataclass(frozen=True)
class TruthInterval:
    truth_interval_id: str
    start_timestamp: float
    end_timestamp: float
    tracks: list[ReviewedTrack]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_reviewed_tracks(*, labels_path: Path, diagnostics_root: Path) -> list[ReviewedTrack]:
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    tracks: list[ReviewedTrack] = []
    for key, row in payload.items():
        if not isinstance(row, dict):
            continue
        diagnostic_id, raw_track_id = str(key).split("|", 1)
        track_id = int(raw_track_id)
        receipt_path = diagnostics_root / diagnostic_id / "track_receipts" / f"track-{track_id:06d}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        timestamps = receipt.get("timestamps") or {}
        start_timestamp = float(timestamps["first"])
        end_timestamp = float(timestamps["last"])
        tracks.append(
            ReviewedTrack(
                diagnostic_id=diagnostic_id,
                track_id=track_id,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                crop_label=str(row.get("crop_label") or ""),
                confidence=str(row.get("confidence") or ""),
                short_reason=str(row.get("short_reason") or ""),
            )
        )
    tracks.sort(key=lambda item: (item.start_timestamp, item.end_timestamp, item.diagnostic_id, item.track_id))
    return tracks


def collapse_truth_intervals(tracks: list[ReviewedTrack], *, gap_seconds: float = 0.0) -> list[TruthInterval]:
    if gap_seconds < 0:
        raise ValueError("gap_seconds must be non-negative")
    if not tracks:
        return []

    intervals: list[TruthInterval] = []
    pending: list[ReviewedTrack] = [tracks[0]]
    start_timestamp = tracks[0].start_timestamp
    end_timestamp = tracks[0].end_timestamp

    def flush() -> None:
        truth_interval_id = f"factory2-truth-{len(intervals) + 1:04d}"
        intervals.append(
            TruthInterval(
                truth_interval_id=truth_interval_id,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                tracks=list(pending),
            )
        )

    for track in tracks[1:]:
        if track.start_timestamp <= end_timestamp + gap_seconds:
            pending.append(track)
            end_timestamp = max(end_timestamp, track.end_timestamp)
            continue
        flush()
        pending = [track]
        start_timestamp = track.start_timestamp
        end_timestamp = track.end_timestamp
    flush()
    return intervals


def load_runtime_events(runtime_audit_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(runtime_audit_path.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    filtered = [event for event in events if isinstance(event, dict) and isinstance(event.get("event_ts"), (int, float))]
    filtered.sort(key=lambda event: (float(event["event_ts"]), int(event.get("track_id") or 0)))
    return filtered


def match_runtime_events(
    truth_intervals: list[TruthInterval],
    runtime_events: list[dict[str, Any]],
    *,
    slack_seconds: float,
) -> dict[str, Any]:
    if slack_seconds < 0:
        raise ValueError("slack_seconds must be non-negative")

    matched_truth_rows: list[dict[str, Any]] = []
    missing_truth_rows: list[dict[str, Any]] = []
    used_event_indexes: set[int] = set()

    for interval in truth_intervals:
        best_index = None
        best_distance = float("inf")
        for index, event in enumerate(runtime_events):
            if index in used_event_indexes:
                continue
            event_ts = float(event["event_ts"])
            if event_ts < interval.start_timestamp - slack_seconds or event_ts > interval.end_timestamp + slack_seconds:
                continue
            center = (interval.start_timestamp + interval.end_timestamp) / 2.0
            distance = abs(event_ts - center)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        track_rows = [asdict(track) for track in interval.tracks]
        if best_index is None:
            missing_truth_rows.append(
                {
                    "truth_interval_id": interval.truth_interval_id,
                    "start_timestamp": round(interval.start_timestamp, 3),
                    "end_timestamp": round(interval.end_timestamp, 3),
                    "track_count": len(interval.tracks),
                    "tracks": track_rows,
                }
            )
            continue
        used_event_indexes.add(best_index)
        event = runtime_events[best_index]
        matched_truth_rows.append(
            {
                "truth_interval_id": interval.truth_interval_id,
                "start_timestamp": round(interval.start_timestamp, 3),
                "end_timestamp": round(interval.end_timestamp, 3),
                "track_count": len(interval.tracks),
                "tracks": track_rows,
                "matched_event": event,
            }
        )

    extra_runtime_events = [event for index, event in enumerate(runtime_events) if index not in used_event_indexes]
    return {
        "matched_truth_count": len(matched_truth_rows),
        "missing_truth_count": len(missing_truth_rows),
        "extra_runtime_event_count": len(extra_runtime_events),
        "matched_truth_intervals": matched_truth_rows,
        "missing_truth_intervals": missing_truth_rows,
        "extra_runtime_events": extra_runtime_events,
    }


def build_truth_gap_report(
    *,
    labels_path: Path,
    runtime_audit_path: Path,
    output_path: Path,
    diagnostics_root: Path,
    gap_seconds: float,
    slack_seconds: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)

    reviewed_tracks = load_reviewed_tracks(labels_path=labels_path, diagnostics_root=diagnostics_root)
    truth_intervals = collapse_truth_intervals(reviewed_tracks, gap_seconds=gap_seconds)
    runtime_events = load_runtime_events(runtime_audit_path)
    diff = match_runtime_events(truth_intervals, runtime_events, slack_seconds=slack_seconds)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "labels_path": str(labels_path),
        "runtime_audit_path": str(runtime_audit_path),
        "diagnostics_root": str(diagnostics_root),
        "truth_track_count": len(reviewed_tracks),
        "truth_interval_count": len(truth_intervals),
        "gap_seconds": gap_seconds,
        "slack_seconds": slack_seconds,
        "truth_intervals": [
            {
                "truth_interval_id": interval.truth_interval_id,
                "start_timestamp": round(interval.start_timestamp, 3),
                "end_timestamp": round(interval.end_timestamp, 3),
                "track_count": len(interval.tracks),
                "tracks": [asdict(track) for track in interval.tracks],
            }
            for interval in truth_intervals
        ],
        **diff,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Factory2 runtime events to the manual truth ledger")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_PATH)
    parser.add_argument("--runtime-audit", type=Path, default=DEFAULT_RUNTIME_AUDIT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--diagnostics-root", type=Path, default=DEFAULT_DIAGNOSTICS_ROOT)
    parser.add_argument("--gap-seconds", type=float, default=0.0)
    parser.add_argument("--slack-seconds", type=float, default=0.75)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_truth_gap_report(
        labels_path=args.labels,
        runtime_audit_path=args.runtime_audit,
        output_path=args.output,
        diagnostics_root=args.diagnostics_root,
        gap_seconds=args.gap_seconds,
        slack_seconds=args.slack_seconds,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "truth_interval_count": payload["truth_interval_count"],
                "matched_truth_count": payload["matched_truth_count"],
                "missing_truth_count": payload["missing_truth_count"],
                "extra_runtime_event_count": payload["extra_runtime_event_count"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
