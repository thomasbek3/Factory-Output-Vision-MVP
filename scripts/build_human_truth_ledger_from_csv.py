#!/usr/bin/env python3
"""Build a timestamped human truth ledger from a simple CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "human-truth-ledger-v1"


def _parse_event_ts(raw_value: str, *, row_number: int) -> float:
    value = raw_value.strip()
    if not value:
        raise ValueError(f"row {row_number}: event_ts is required")
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"row {row_number}: event_ts must be seconds or MM:SS.s")
        minutes = float(parts[0])
        seconds = float(parts[1])
        parsed = minutes * 60.0 + seconds
    else:
        parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"row {row_number}: event_ts must be a non-negative finite number")
    return round(parsed, 3)


def _parse_count_total(raw_value: str, *, row_number: int) -> int:
    value = raw_value.strip()
    if not value:
        raise ValueError(f"row {row_number}: count_total is required")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"row {row_number}: count_total must be positive")
    return parsed


def read_truth_events(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"truth_event_id", "count_total", "event_ts"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"{csv_path} missing columns: {', '.join(sorted(missing_columns))}")

        events: list[dict[str, Any]] = []
        for row_number, row in enumerate(reader, start=2):
            truth_event_id = (row.get("truth_event_id") or "").strip()
            if not truth_event_id:
                raise ValueError(f"row {row_number}: truth_event_id is required")
            events.append(
                {
                    "truth_event_id": truth_event_id,
                    "count_total": _parse_count_total(row.get("count_total") or "", row_number=row_number),
                    "event_ts": _parse_event_ts(row.get("event_ts") or "", row_number=row_number),
                    "notes": (row.get("notes") or "").strip(),
                }
            )

    events.sort(key=lambda event: (event["event_ts"], event["count_total"]))
    for index, event in enumerate(events, start=1):
        if event["count_total"] != index:
            raise ValueError(
                f"event {event['truth_event_id']}: count_total {event['count_total']} "
                f"does not match sorted position {index}"
            )
    return events


def build_ledger(
    *,
    csv_path: Path,
    output_path: Path,
    video_path: Path,
    expected_total: int,
    count_rule: str,
    video_sha256: str | None,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if expected_total <= 0:
        raise ValueError("--expected-total must be positive")

    events = read_truth_events(csv_path)
    if len(events) != expected_total:
        raise ValueError(f"expected {expected_total} events, found {len(events)} in {csv_path}")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "video_path": str(video_path),
        "video_sha256": video_sha256,
        "expected_human_total": expected_total,
        "counting_rule": count_rule,
        "source_csv_path": str(csv_path),
        "events": events,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a timestamped human truth ledger from CSV")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--expected-total", type=int, required=True)
    parser.add_argument("--count-rule", required=True)
    parser.add_argument("--video-sha256")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_ledger(
        csv_path=args.csv,
        output_path=args.output,
        video_path=args.video,
        expected_total=args.expected_total,
        count_rule=args.count_rule,
        video_sha256=args.video_sha256,
        force=args.force,
    )
    print(json.dumps({"output": str(args.output), "event_count": len(payload["events"])}))


if __name__ == "__main__":
    main()
