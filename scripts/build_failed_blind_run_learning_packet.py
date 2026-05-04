#!/usr/bin/env python3
"""Build a learning review packet from a failed blind diagnostic run."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import time
from pathlib import Path
from typing import Any


EOF_EVENT_REASON = "end_of_stream_active_track_event"
SCHEMA_VERSION = "factory-vision-failed-blind-run-learning-packet-v1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _nearest_motion_window(event_ts: float, motion_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not motion_events:
        return None
    return min(
        motion_events,
        key=lambda event: abs(float(event.get("center_timestamp") or 0.0) - event_ts),
    )


def _motion_window_ref(window: dict[str, Any] | None) -> dict[str, Any] | None:
    if window is None:
        return None
    return {
        "event_id": window.get("event_id"),
        "center_timestamp": window.get("center_timestamp"),
        "start_timestamp": window.get("start_timestamp"),
        "end_timestamp": window.get("end_timestamp"),
        "score": window.get("score"),
        "sheet_path": window.get("sheet_path"),
        "clip_path": window.get("clip_path"),
    }


def build_truth_review_slots(*, case_id: str, expected_true_total: int) -> list[dict[str, Any]]:
    return [
        {
            "slot_id": f"{case_id}-truth-slot-{index:04d}",
            "candidate_type": "true_placement_slot",
            "review_status": "pending",
            "review_decision": "",
            "reviewed_event_ts": None,
            "sheet_path": None,
            "clip_path": None,
            "label_authority_tier": "bronze",
            "validation_truth_eligible": False,
            "training_eligible": False,
            "notes": "Fill this slot only after human review identifies one real completed placement.",
        }
        for index in range(1, expected_true_total + 1)
    ]


def build_false_positive_candidates(
    *,
    case_id: str,
    diagnostic: dict[str, Any],
    motion_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, event in enumerate(
        [item for item in diagnostic.get("events", []) if item.get("reason") != EOF_EVENT_REASON],
        start=1,
    ):
        event_ts = float(event.get("event_ts") or 0.0)
        nearest = _nearest_motion_window(event_ts, motion_events)
        nearest_ref = _motion_window_ref(nearest)
        candidates.append(
            {
                "candidate_id": f"{case_id}-hard-negative-{index:04d}",
                "candidate_type": "runtime_false_positive_candidate",
                "event_ts": event_ts,
                "track_id": event.get("track_id"),
                "reason": event.get("reason"),
                "travel_px": event.get("travel_px"),
                "frames_seen": event.get("frames_seen"),
                "centroid": event.get("centroid"),
                "runtime_total_after_event": event.get("runtime_total_after_event"),
                "nearest_motion_window": nearest_ref,
                "sheet_path": nearest_ref.get("sheet_path") if nearest_ref else None,
                "clip_path": nearest_ref.get("clip_path") if nearest_ref else None,
                "suggested_review_decision": "hard_negative_static_or_duplicate",
                "review_status": "pending",
                "label_authority_tier": "bronze",
                "validation_truth_eligible": False,
                "training_eligible": False,
            }
        )
    return candidates


def build_motion_window_candidates(
    *,
    case_id: str,
    motion_events: list[dict[str, Any]],
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = motion_events if limit is None else motion_events[:limit]
    return [
        {
            "candidate_id": f"{case_id}-motion-window-{index:04d}",
            "candidate_type": "possible_true_or_missed_event_window",
            "motion_event_id": event.get("event_id"),
            "center_timestamp": event.get("center_timestamp"),
            "start_timestamp": event.get("start_timestamp"),
            "end_timestamp": event.get("end_timestamp"),
            "score": event.get("score"),
            "selection_reason": event.get("selection_reason"),
            "sheet_path": event.get("sheet_path"),
            "clip_path": event.get("clip_path"),
            "review_status": "pending",
            "review_decision": "",
            "label_authority_tier": "bronze",
            "validation_truth_eligible": False,
            "training_eligible": False,
        }
        for index, event in enumerate(selected, start=1)
    ]


def build_packet(
    *,
    case_id: str,
    expected_true_total: int,
    motion_windows_path: Path,
    diagnostic_path: Path,
    viability_path: Path,
    motion_window_limit: int | None = None,
) -> dict[str, Any]:
    motion_windows = read_json(motion_windows_path)
    diagnostic = read_json(diagnostic_path)
    viability = read_json(viability_path)
    motion_events = list(motion_windows.get("events", []))
    truth_slots = build_truth_review_slots(case_id=case_id, expected_true_total=expected_true_total)
    false_positive_candidates = build_false_positive_candidates(
        case_id=case_id,
        diagnostic=diagnostic,
        motion_events=motion_events,
    )
    motion_window_candidates = build_motion_window_candidates(
        case_id=case_id,
        motion_events=motion_events,
        limit=motion_window_limit,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "created_at": round(time.time(), 3),
        "privacy_mode": "offline_local",
        "expected_true_total": expected_true_total,
        "source_paths": {
            "motion_windows": motion_windows_path.as_posix(),
            "runtime_diagnostic": diagnostic_path.as_posix(),
            "blind_prediction_viability": viability_path.as_posix(),
        },
        "authority_boundary": {
            "review_status": "pending_human_review",
            "validation_truth_eligible": False,
            "training_eligible": False,
            "teacher_or_runtime_labels_are_truth": False,
        },
        "blind_prediction_viability": {
            "status": viability.get("status"),
            "numeric_prediction_allowed": viability.get("numeric_prediction_allowed"),
            "recommendation": viability.get("recommendation"),
        },
        "truth_review_slots": truth_slots,
        "false_positive_candidates": false_positive_candidates,
        "motion_window_candidates": motion_window_candidates,
        "review_requirements": {
            "accepted_true_placement_count_required": expected_true_total,
            "hard_negative_review_required": True,
            "can_build_gold_truth_before_review": False,
            "can_train_before_review": False,
        },
    }


def _csv_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot in packet["truth_review_slots"]:
        rows.append(
            {
                "row_type": slot["candidate_type"],
                "candidate_id": slot["slot_id"],
                "source_id": "",
                "center_timestamp": "",
                "start_timestamp": "",
                "end_timestamp": "",
                "runtime_track_id": "",
                "runtime_travel_px": "",
                "suggested_review_decision": "",
                "review_decision": "",
                "reviewed_event_ts": "",
                "sheet_path": "",
                "clip_path": "",
                "notes": slot["notes"],
            }
        )
    for candidate in packet["false_positive_candidates"]:
        nearest = candidate.get("nearest_motion_window") or {}
        rows.append(
            {
                "row_type": candidate["candidate_type"],
                "candidate_id": candidate["candidate_id"],
                "source_id": candidate.get("track_id") or "",
                "center_timestamp": candidate.get("event_ts") or "",
                "start_timestamp": nearest.get("start_timestamp") or "",
                "end_timestamp": nearest.get("end_timestamp") or "",
                "runtime_track_id": candidate.get("track_id") or "",
                "runtime_travel_px": candidate.get("travel_px") or "",
                "suggested_review_decision": candidate["suggested_review_decision"],
                "review_decision": "",
                "reviewed_event_ts": "",
                "sheet_path": candidate.get("sheet_path") or "",
                "clip_path": candidate.get("clip_path") or "",
                "notes": "Runtime false-positive candidate from failed static-detector diagnostic.",
            }
        )
    for candidate in packet["motion_window_candidates"]:
        rows.append(
            {
                "row_type": candidate["candidate_type"],
                "candidate_id": candidate["candidate_id"],
                "source_id": candidate.get("motion_event_id") or "",
                "center_timestamp": candidate.get("center_timestamp") or "",
                "start_timestamp": candidate.get("start_timestamp") or "",
                "end_timestamp": candidate.get("end_timestamp") or "",
                "runtime_track_id": "",
                "runtime_travel_px": "",
                "suggested_review_decision": "review_for_true_placement_or_background",
                "review_decision": "",
                "reviewed_event_ts": "",
                "sheet_path": candidate.get("sheet_path") or "",
                "clip_path": candidate.get("clip_path") or "",
                "notes": "Motion-mined candidate window; review may identify one of the 4 true placements or a hard negative.",
            }
        )
    return rows


def write_csv(path: Path, packet: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _csv_rows(packet)
    fieldnames = [
        "row_type",
        "candidate_id",
        "source_id",
        "center_timestamp",
        "start_timestamp",
        "end_timestamp",
        "runtime_track_id",
        "runtime_travel_px",
        "suggested_review_decision",
        "review_decision",
        "reviewed_event_ts",
        "sheet_path",
        "clip_path",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _asset_src(path: str | None, *, output_path: Path) -> str:
    if not path:
        return ""
    raw_path = Path(path)
    absolute = raw_path if raw_path.is_absolute() else raw_path.resolve()
    relative = os.path.relpath(absolute, start=output_path.parent.resolve())
    return relative.replace(os.sep, "/")


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _candidate_card(candidate: dict[str, Any], *, output_path: Path) -> str:
    sheet_src = _asset_src(candidate.get("sheet_path"), output_path=output_path)
    clip_src = _asset_src(candidate.get("clip_path"), output_path=output_path)
    image = (
        f'<img src="{html.escape(sheet_src)}" alt="{html.escape(str(candidate.get("candidate_id")))}" loading="lazy">'
        if sheet_src
        else '<div class="missing">No sheet</div>'
    )
    clip = f'<a href="{html.escape(clip_src)}">clip</a>' if clip_src else ""
    timestamp = candidate.get("event_ts", candidate.get("center_timestamp"))
    detail_parts = [
        f"type={candidate.get('candidate_type')}",
        f"t={_display(timestamp)}",
        f"travel={_display(candidate.get('travel_px'))}",
        f"track={_display(candidate.get('track_id'))}",
    ]
    return f"""
    <article class="card">
      <div class="media">{image}</div>
      <div class="body">
        <h2>{html.escape(str(candidate.get("candidate_id")))}</h2>
        <div class="meta">{html.escape(" | ".join(part for part in detail_parts if not part.endswith("=")))}</div>
        <div class="decision">Review decision:
          <select>
            <option></option>
            <option>true_placement</option>
            <option>hard_negative_static</option>
            <option>duplicate</option>
            <option>worker_motion_only</option>
            <option>unclear</option>
          </select>
          <label>event ts <input type="text" placeholder="seconds"></label>
          {clip}
        </div>
      </div>
    </article>
    """


def build_html(packet: dict[str, Any], *, output_path: Path) -> str:
    false_cards = "\n".join(
        _candidate_card(candidate, output_path=output_path)
        for candidate in packet["false_positive_candidates"]
    )
    motion_cards = "\n".join(
        _candidate_card(candidate, output_path=output_path)
        for candidate in packet["motion_window_candidates"]
    )
    case_id = html.escape(str(packet["case_id"]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Factory Vision Failed Blind Run Review - {case_id}</title>
  <style>
    :root {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1e2320;
      background: #f6f7f4;
    }}
    body {{ margin: 0; }}
    header {{ padding: 22px 28px; background: #fff; border-bottom: 1px solid #d7ddd5; position: sticky; top: 0; z-index: 2; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 15px; margin: 0 0 8px; letter-spacing: 0; overflow-wrap: anywhere; }}
    .warning {{ color: #7a3f00; font-weight: 650; font-size: 13px; line-height: 1.45; }}
    .summary {{ color: #4d5751; font-size: 13px; line-height: 1.5; }}
    section {{ padding: 18px; }}
    section > h2 {{ font-size: 18px; margin: 0 0 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }}
    .card {{ background: #fff; border: 1px solid #d7ddd5; border-radius: 8px; overflow: hidden; min-width: 0; }}
    .media {{ aspect-ratio: 16 / 9; background: #111; display: flex; align-items: center; justify-content: center; }}
    img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .missing {{ color: #fff; font-size: 13px; }}
    .body {{ padding: 12px; }}
    .meta {{ font-size: 12px; color: #536057; margin-bottom: 10px; overflow-wrap: anywhere; }}
    .decision {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; }}
    input, select {{ font: inherit; max-width: 160px; }}
    a {{ color: #135f8a; }}
  </style>
</head>
<body>
  <header>
    <h1>Failed Blind Run Learning Review</h1>
    <div class="summary">Case: {case_id} | expected true placements: {packet["expected_true_total"]} | false-positive candidates: {len(packet["false_positive_candidates"])} | motion windows: {len(packet["motion_window_candidates"])}</div>
    <div class="warning">Pending review only. This packet is not validation truth and is not training eligible until reviewed labels are promoted.</div>
  </header>
  <section>
    <h2>Runtime False-Positive Candidates</h2>
    <div class="grid">{false_cards}</div>
  </section>
  <section>
    <h2>Motion Windows To Find The 4 True Placements</h2>
    <div class="grid">{motion_cards}</div>
  </section>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review artifacts from a failed blind diagnostic run")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--expected-true-total", type=int, required=True)
    parser.add_argument("--motion-windows", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--viability", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument("--motion-window-limit", type=int)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    packet = build_packet(
        case_id=args.case_id,
        expected_true_total=args.expected_true_total,
        motion_windows_path=args.motion_windows,
        diagnostic_path=args.diagnostic,
        viability_path=args.viability,
        motion_window_limit=args.motion_window_limit,
    )
    write_json(args.output_json, packet, force=args.force)
    write_csv(args.output_csv, packet, force=args.force)
    write_text(args.output_html, build_html(packet, output_path=args.output_html), force=args.force)
    print(
        json.dumps(
            {
                "output_json": args.output_json.as_posix(),
                "output_csv": args.output_csv.as_posix(),
                "output_html": args.output_html.as_posix(),
                "false_positive_candidates": len(packet["false_positive_candidates"]),
                "motion_window_candidates": len(packet["motion_window_candidates"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
