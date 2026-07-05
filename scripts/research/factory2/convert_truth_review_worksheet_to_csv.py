#!/usr/bin/env python3
"""Convert a filled human review worksheet into a truth-event CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any


ACCEPT_VALUES = {"1", "true", "yes", "y", "countable", "accepted", "accept"}
REJECT_VALUES = {"0", "false", "no", "n", "reject", "rejected", "not_countable", "skip"}
REQUIRED_COLUMNS = {
    "candidate_id",
    "human_decision_accept_countable",
    "exact_event_ts",
}


def _parse_event_ts(raw_value: str, *, row_number: int) -> float:
    value = raw_value.strip()
    if not value:
        raise ValueError(f"row {row_number}: exact_event_ts is required for accepted rows")
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"row {row_number}: exact_event_ts must be seconds or MM:SS.s")
        minutes = float(parts[0])
        seconds = float(parts[1])
        parsed = minutes * 60.0 + seconds
    else:
        parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"row {row_number}: exact_event_ts must be a non-negative finite number")
    return round(parsed, 3)


def _decision(raw_value: str, *, row_number: int) -> bool | None:
    value = raw_value.strip().lower()
    if not value:
        return None
    if value in ACCEPT_VALUES:
        return True
    if value in REJECT_VALUES:
        return False
    raise ValueError(f"row {row_number}: unrecognized human_decision_accept_countable value {raw_value!r}")


def _maybe_int(raw_value: str) -> int | None:
    value = raw_value.strip()
    if not value:
        return None
    return int(value)


def read_accepted_events(
    worksheet_path: Path,
    *,
    expected_total: int,
    truth_event_prefix: str,
) -> list[dict[str, Any]]:
    if expected_total <= 0:
        raise ValueError("expected_total must be positive")

    with worksheet_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"{worksheet_path} missing columns: {', '.join(sorted(missing_columns))}")

        accepted_rows: list[dict[str, Any]] = []
        pending_count = 0
        for row_number, row in enumerate(reader, start=2):
            decision = _decision(row.get("human_decision_accept_countable") or "", row_number=row_number)
            if decision is None:
                pending_count += 1
                continue
            if not decision:
                continue
            accepted_rows.append(
                {
                    "source_row_number": row_number,
                    "candidate_id": (row.get("candidate_id") or "").strip(),
                    "event_ts": _parse_event_ts(row.get("exact_event_ts") or "", row_number=row_number),
                    "requested_truth_event_id": (row.get("truth_event_id_if_accepted") or "").strip(),
                    "requested_count_total": _maybe_int(row.get("count_total_if_accepted") or ""),
                    "reviewer": (row.get("reviewer") or "").strip(),
                    "review_notes": (row.get("review_notes") or "").strip(),
                }
            )

    if pending_count:
        raise ValueError(f"worksheet still has {pending_count} pending row(s); every row must be accepted or rejected")
    if len(accepted_rows) != expected_total:
        raise ValueError(f"expected {expected_total} accepted rows, found {len(accepted_rows)}")

    accepted_rows.sort(key=lambda item: (item["event_ts"], item["source_row_number"]))
    events: list[dict[str, Any]] = []
    for index, row in enumerate(accepted_rows, start=1):
        requested_count_total = row["requested_count_total"]
        if requested_count_total is not None and requested_count_total != index:
            raise ValueError(
                f"row {row['source_row_number']}: count_total_if_accepted {requested_count_total} "
                f"does not match sorted accepted event position {index}"
            )
        truth_event_id = row["requested_truth_event_id"] or f"{truth_event_prefix}-{index:04d}"
        note_parts = [f"source_candidate={row['candidate_id']}"]
        if row["reviewer"]:
            note_parts.append(f"reviewer={row['reviewer']}")
        if row["review_notes"]:
            note_parts.append(row["review_notes"])
        events.append(
            {
                "truth_event_id": truth_event_id,
                "count_total": index,
                "event_ts": row["event_ts"],
                "notes": "; ".join(note_parts),
            }
        )
    return events


def write_truth_csv(events: list[dict[str, Any]], output_path: Path, *, force: bool) -> None:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["truth_event_id", "count_total", "event_ts", "notes"])
        writer.writeheader()
        for event in events:
            writer.writerow(event)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a completed human review worksheet into a truth-event CSV"
    )
    parser.add_argument("--worksheet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-total", type=int, required=True)
    parser.add_argument("--truth-event-prefix", default="truth-event")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        events = read_accepted_events(
            args.worksheet,
            expected_total=args.expected_total,
            truth_event_prefix=args.truth_event_prefix,
        )
        write_truth_csv(events, args.output, force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "event_count": len(events)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
