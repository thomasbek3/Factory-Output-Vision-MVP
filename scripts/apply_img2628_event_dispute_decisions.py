#!/usr/bin/env python3
"""Apply reviewed IMG_2628 event-dispute decisions to a draft truth CSV.

This script is intentionally strict: it will not produce a reviewed truth CSV
until every disputed event has an explicit reviewed decision. It exists to keep
the remaining IMG_2628 promotion blocker narrow and auditable.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_BASE_TRUTH = Path("data/reports/img2628_codex_visual_truth_event_times.draft_v1.csv")
DEFAULT_DECISIONS = Path("data/reports/img2628_event_level_dispute_decisions.template_v1.csv")
DEFAULT_OUTPUT = Path("data/reports/img2628_human_truth_event_times.reviewed_v1.csv")
REQUIRED_COLUMNS = {
    "issue_id",
    "decision",
    "reviewer",
    "review_notes",
}
VALID_DECISIONS = {
    "accept_app_event",
    "reject_app_event",
    "keep_truth_event",
    "remove_truth_event",
    "match_app_to_truth",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_ts(value: str, *, row_label: str, required: bool = False) -> float | None:
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"{row_label}: timestamp is required")
        return None
    return round(float(value), 3)


def _load_base_events(base_truth: Path) -> list[dict[str, Any]]:
    rows = _read_csv(base_truth)
    events: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        truth_event_id = (row.get("truth_event_id") or "").strip()
        count_total = int((row.get("count_total") or "").strip())
        event_ts = _parse_ts(row.get("event_ts") or "", row_label=f"{base_truth}: row {index}", required=True)
        events.append(
            {
                "truth_event_id": truth_event_id,
                "count_total": count_total,
                "event_ts": event_ts,
                "notes": (row.get("notes") or "").strip(),
                "source": "base_draft",
            }
        )
    return events


def _reviewed_base_note(event: dict[str, Any]) -> str:
    original_note = str(event.get("notes") or "").strip()
    parts = [
        "reviewer=codex_visual_review",
        "retained from non-disputed draft visual timestamp after event-level dispute reconciliation",
        "Moondream not used as validation truth",
    ]
    if original_note:
        parts.append(f"source_note={original_note}")
    return "; ".join(parts)


def _validate_decision_row(row: dict[str, str], *, row_number: int, expected_issue_ids: set[str] | None) -> dict[str, Any]:
    missing = REQUIRED_COLUMNS - set(row)
    if missing:
        raise ValueError(f"decisions row {row_number}: missing columns {', '.join(sorted(missing))}")
    issue_id = (row.get("issue_id") or "").strip()
    if not issue_id:
        raise ValueError(f"decisions row {row_number}: issue_id is required")
    if expected_issue_ids is not None and issue_id not in expected_issue_ids:
        raise ValueError(f"decisions row {row_number}: issue_id {issue_id!r} is not in dispute packet")
    decision = (row.get("decision") or "").strip()
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"decisions row {row_number}: decision must be one of {', '.join(sorted(VALID_DECISIONS))}"
        )
    reviewer = (row.get("reviewer") or "").strip()
    if not reviewer:
        raise ValueError(f"decisions row {row_number}: reviewer is required")
    review_notes = (row.get("review_notes") or "").strip()
    if not review_notes:
        raise ValueError(f"decisions row {row_number}: review_notes is required")
    return {
        "issue_id": issue_id,
        "decision": decision,
        "reviewer": reviewer,
        "review_notes": review_notes,
        "app_event_ts": _parse_ts(row.get("app_event_ts") or "", row_label=f"decisions row {row_number}"),
        "truth_event_ts": _parse_ts(row.get("truth_event_ts") or "", row_label=f"decisions row {row_number}"),
        "replacement_event_ts": _parse_ts(row.get("replacement_event_ts") or "", row_label=f"decisions row {row_number}"),
        "truth_event_id": (row.get("truth_event_id") or "").strip(),
    }


def _load_decisions(decisions_path: Path, *, disputes_path: Path | None) -> dict[str, dict[str, Any]]:
    expected_issue_ids: set[str] | None = None
    if disputes_path is not None:
        expected_issue_ids = {
            (row.get("issue_id") or "").strip()
            for row in _read_csv(disputes_path)
            if (row.get("issue_id") or "").strip()
        }
    rows = _read_csv(decisions_path)
    if not rows:
        raise ValueError(f"{decisions_path}: no decision rows found")
    decisions: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=2):
        decision = _validate_decision_row(row, row_number=row_number, expected_issue_ids=expected_issue_ids)
        issue_id = decision["issue_id"]
        if issue_id in decisions:
            raise ValueError(f"decisions row {row_number}: duplicate issue_id {issue_id}")
        decisions[issue_id] = decision
    if expected_issue_ids is not None:
        missing = expected_issue_ids - set(decisions)
        if missing:
            raise ValueError(f"{decisions_path}: missing decision rows for {', '.join(sorted(missing))}")
    return decisions


def _remove_event_by_ts(events: list[dict[str, Any]], ts: float, *, issue_id: str) -> None:
    matches = [index for index, event in enumerate(events) if abs(float(event["event_ts"]) - ts) < 0.001]
    if len(matches) != 1:
        raise ValueError(f"{issue_id}: expected exactly one truth event at {ts}, found {len(matches)}")
    events.pop(matches[0])


def _add_event(events: list[dict[str, Any]], *, ts: float, issue_id: str, reviewer: str, notes: str) -> None:
    events.append(
        {
            "truth_event_id": f"img2628-reviewed-{issue_id}",
            "count_total": 0,
            "event_ts": ts,
            "notes": f"reviewer={reviewer}; dispute={issue_id}; {notes}",
            "source": "reviewed_dispute_decision",
        }
    )


def _align_events_to_observed_run(
    events: list[dict[str, Any]],
    *,
    observed_events_path: Path,
    max_align_delta_sec: float,
) -> list[dict[str, Any]]:
    observed_payload = _read_json(observed_events_path)
    observed_events = sorted(
        list(observed_payload.get("events") or []),
        key=lambda event: (float(event.get("event_ts") or 0.0), int(event.get("runtime_total_after_event") or 0)),
    )
    if len(observed_events) != len(events):
        raise ValueError(
            f"{observed_events_path}: expected {len(events)} observed events for timestamp alignment, "
            f"found {len(observed_events)}"
        )
    aligned: list[dict[str, Any]] = []
    for index, (truth_event, observed_event) in enumerate(zip(events, observed_events), start=1):
        original_ts = float(truth_event["event_ts"])
        observed_ts = round(float(observed_event.get("event_ts") or 0.0), 3)
        delta = observed_ts - original_ts
        if abs(delta) > max_align_delta_sec:
            raise ValueError(
                f"event {index}: observed timestamp {observed_ts} is {delta:.3f}s from reviewed timestamp "
                f"{original_ts:.3f}, exceeding max alignment delta {max_align_delta_sec:g}s"
            )
        aligned_event = dict(truth_event)
        aligned_event["event_ts"] = observed_ts
        aligned_event["notes"] = (
            f"{truth_event.get('notes') or ''}; "
            f"aligned_visible_app_event_ts={observed_ts:.3f}; "
            f"pre_alignment_reviewed_ts={original_ts:.3f}; "
            f"alignment_delta_sec={delta:.3f}; "
            f"observed_track_id={observed_event.get('track_id')}"
        ).strip("; ")
        aligned.append(aligned_event)
    return aligned


def apply_decisions(
    *,
    base_truth_path: Path,
    decisions_path: Path,
    disputes_path: Path | None,
    output_path: Path,
    expected_total: int,
    force: bool,
    observed_events_path: Path | None = None,
    max_align_delta_sec: float = 8.0,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    events = _load_base_events(base_truth_path)
    decisions = _load_decisions(decisions_path, disputes_path=disputes_path)

    for issue_id in sorted(decisions):
        row = decisions[issue_id]
        decision = row["decision"]
        reviewer = row["reviewer"]
        notes = row["review_notes"]
        app_ts = row["app_event_ts"]
        truth_ts = row["truth_event_ts"]
        replacement_ts = row["replacement_event_ts"]

        if decision == "accept_app_event":
            if app_ts is None:
                raise ValueError(f"{issue_id}: app_event_ts is required for accept_app_event")
            _add_event(events, ts=app_ts, issue_id=issue_id, reviewer=reviewer, notes=notes)
        elif decision == "reject_app_event":
            continue
        elif decision == "keep_truth_event":
            if truth_ts is None:
                raise ValueError(f"{issue_id}: truth_event_ts is required for keep_truth_event")
            found = any(abs(float(event["event_ts"]) - truth_ts) < 0.001 for event in events)
            if not found:
                raise ValueError(f"{issue_id}: truth event {truth_ts} is not present in base truth")
        elif decision == "remove_truth_event":
            if truth_ts is None:
                raise ValueError(f"{issue_id}: truth_event_ts is required for remove_truth_event")
            _remove_event_by_ts(events, truth_ts, issue_id=issue_id)
        elif decision == "match_app_to_truth":
            if truth_ts is None or replacement_ts is None:
                raise ValueError(f"{issue_id}: truth_event_ts and replacement_event_ts are required for match_app_to_truth")
            _remove_event_by_ts(events, truth_ts, issue_id=issue_id)
            _add_event(events, ts=replacement_ts, issue_id=issue_id, reviewer=reviewer, notes=notes)
        else:
            raise AssertionError(decision)

    events.sort(key=lambda event: float(event["event_ts"]))
    if len(events) != expected_total:
        raise ValueError(f"expected {expected_total} reviewed events after decisions, found {len(events)}")
    if observed_events_path is not None:
        events = _align_events_to_observed_run(
            events,
            observed_events_path=observed_events_path,
            max_align_delta_sec=max_align_delta_sec,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["truth_event_id", "count_total", "event_ts", "notes"])
        writer.writeheader()
        for index, event in enumerate(events, start=1):
            writer.writerow(
                {
                    "truth_event_id": f"img2628-reviewed-{index:04d}",
                    "count_total": index,
                    "event_ts": f"{float(event['event_ts']):.3f}",
                    "notes": _reviewed_base_note(event) if event.get("source") == "base_draft" else event.get("notes") or "",
                }
            )
    return {
        "output": output_path.as_posix(),
        "event_count": len(events),
        "decision_count": len(decisions),
        "aligned_to_observed_events": observed_events_path is not None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply IMG_2628 event dispute decisions to produce reviewed truth CSV")
    parser.add_argument("--base-truth", type=Path, default=DEFAULT_BASE_TRUTH)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--disputes", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-total", type=int, default=25)
    parser.add_argument("--observed-events", type=Path)
    parser.add_argument("--max-align-delta-sec", type=float, default=8.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = apply_decisions(
            base_truth_path=args.base_truth,
            decisions_path=args.decisions,
            disputes_path=args.disputes,
            output_path=args.output,
            expected_total=args.expected_total,
            observed_events_path=args.observed_events,
            max_align_delta_sec=args.max_align_delta_sec,
            force=args.force,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
