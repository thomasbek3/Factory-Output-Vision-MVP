from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_event_proposer import build_event_proposals
from app.services.station_calibration import read_station_calibration
from app.services.stream_recorder import validate_segment_manifest


DEFAULT_EXAM_START = datetime.strptime("20260611T152150", "%Y%m%dT%H%M%S")
DEFAULT_EXAM_END = datetime.strptime("20260611T162733", "%Y%m%dT%H%M%S")
PASS_THRESHOLD = 6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate wide-net miner recall against held-out exam positives")
    parser.add_argument("--segment-manifest", type=Path, required=True)
    parser.add_argument("--gold-positives", type=Path, required=True)
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--proposal-mode", choices=["output_zone_motion"], default="output_zone_motion")
    parser.add_argument("--zone-motion-threshold", type=float, default=0.018)
    parser.add_argument("--min-flash-ratio", type=float, default=1.5)
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        report = run_recall_gate(
            segment_manifest_path=args.segment_manifest,
            gold_positives_path=args.gold_positives,
            station_calibration_path=args.station_calibration,
            proposal_mode=args.proposal_mode,
            zone_motion_threshold=args.zone_motion_threshold,
            min_flash_ratio=args.min_flash_ratio,
            match_tolerance_sec=args.match_tolerance_sec,
            out_path=args.out,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    print(_format_table(report))
    return 0 if report["verdict"] == "PASS" else 1


def run_recall_gate(
    *,
    segment_manifest_path: Path,
    gold_positives_path: Path,
    station_calibration_path: Path,
    proposal_mode: str,
    zone_motion_threshold: float,
    min_flash_ratio: float,
    match_tolerance_sec: float,
    out_path: Path,
) -> dict[str, Any]:
    gold_payload = json.loads(gold_positives_path.read_text(encoding="utf-8"))
    gold_events = load_gold_events(gold_payload)
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    validate_segment_manifest(manifest)
    exam_start, exam_end = exam_window_for_manifest(gold_events=gold_events, manifest=manifest)
    exam_manifest = filter_manifest_to_exam_window(manifest=manifest, exam_start=exam_start, exam_end=exam_end)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    exam_manifest_path = out_path.parent / "exam_hour_segment_manifest.json"
    exam_manifest_path.write_text(json.dumps(exam_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    calibration = read_station_calibration(station_calibration_path)
    output_polygons = calibration.get("output_polygons") or []
    if not output_polygons:
        raise ValueError("station calibration must include at least one output polygon")

    proposals_payload = build_event_proposals(
        segment_manifest_path=exam_manifest_path,
        output_zone_polygon=output_polygons[0],
        proposal_mode=proposal_mode,
        zone_motion_threshold=zone_motion_threshold,
        min_flash_ratio=min_flash_ratio,
        stable_negative_count=0,
    )
    report = build_recall_report(
        proposals_payload=proposals_payload,
        gold_events=gold_events,
        exam_start=exam_start,
        exam_end=exam_end,
        match_tolerance_sec=match_tolerance_sec,
        config={
            "segment_manifest": str(segment_manifest_path),
            "gold_positives": str(gold_positives_path),
            "station_calibration": str(station_calibration_path),
            "proposal_mode": proposal_mode,
            "zone_motion_threshold": zone_motion_threshold,
            "min_flash_ratio": min_flash_ratio,
            "match_tolerance_sec": match_tolerance_sec,
            "exam_hour_manifest": str(exam_manifest_path),
        },
    )
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def load_gold_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema") != "exam_gold_positives_v1":
        raise ValueError(f"unsupported gold positives schema: {payload.get('schema')}")
    events = []
    for row in payload.get("events") or []:
        event = dict(row)
        event["wall_time"] = gold_event_wall_time(event)
        events.append(event)
    if not events:
        raise ValueError("gold positives must include at least one event")
    return events


def gold_event_wall_time(event: dict[str, Any]) -> datetime:
    return segment_filename_start(str(event["segment_file"])) + timedelta(seconds=float(event["offset_in_segment_sec"]))


def exam_window_for_manifest(*, gold_events: list[dict[str, Any]], manifest: dict[str, Any]) -> tuple[datetime, datetime]:
    segment_starts = {segment_filename_start(str(row["path"])) for row in manifest.get("segments") or []}
    if DEFAULT_EXAM_START in segment_starts and DEFAULT_EXAM_END in segment_starts:
        return DEFAULT_EXAM_START, DEFAULT_EXAM_END
    gold_times = [event["wall_time"] for event in gold_events]
    return min(gold_times), max(gold_times)


def filter_manifest_to_exam_window(
    *,
    manifest: dict[str, Any],
    exam_start: datetime,
    exam_end: datetime,
) -> dict[str, Any]:
    rows = [
        row
        for row in manifest.get("segments") or []
        if exam_start <= segment_filename_start(str(row["path"])) <= exam_end
    ]
    filtered = dict(manifest)
    filtered["segments"] = rows
    filtered["exam_recall_gate"] = {
        "exam_start": exam_start.isoformat(),
        "exam_end": exam_end.isoformat(),
        "input_segment_count": len(manifest.get("segments") or []),
        "exam_segment_count": len(rows),
    }
    validate_segment_manifest(filtered)
    return filtered


def build_recall_report(
    *,
    proposals_payload: dict[str, Any],
    gold_events: list[dict[str, Any]],
    exam_start: datetime,
    exam_end: datetime,
    match_tolerance_sec: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    candidates = [
        row
        for row in proposals_payload.get("proposals") or []
        if row.get("candidate_type") == "event_candidate"
    ]
    candidate_times = [(row, proposal_center_wall_time(row)) for row in candidates]
    rows = []
    caught_count = 0
    for event in gold_events:
        nearest_row, nearest_delta_sec = nearest_candidate(event["wall_time"], candidate_times)
        caught = nearest_delta_sec is not None and abs(nearest_delta_sec) <= match_tolerance_sec
        if caught:
            caught_count += 1
        rows.append(
            {
                "id": event["id"],
                "gold_wall_time": event["wall_time"].isoformat(),
                "caught": caught,
                "nearest_candidate_id": None if nearest_row is None else nearest_row.get("candidate_id"),
                "nearest_delta_sec": nearest_delta_sec,
            }
        )
    total = len(gold_events)
    verdict = "PASS" if caught_count >= PASS_THRESHOLD else "FAIL"
    return {
        "schema_version": "factory-vision-miner-recall-gate-v1",
        "verdict": verdict,
        "pass_threshold": PASS_THRESHOLD,
        "failure_next_step": None
        if verdict == "PASS"
        else "Motion mining alone is insufficient; escalate to the layer-2 state-change miner.",
        "config": config,
        "exam_window": {
            "start": exam_start.isoformat(),
            "end": exam_end.isoformat(),
        },
        "summary": {
            "caught": caught_count,
            "total_gold": total,
            "candidate_count": len(candidates),
            "dropped_low_flash_ratio": int(proposals_payload.get("summary", {}).get("dropped_low_flash_ratio") or 0),
        },
        "gold_results": rows,
    }


def nearest_candidate(
    gold_time: datetime,
    candidate_times: list[tuple[dict[str, Any], datetime]],
) -> tuple[dict[str, Any] | None, float | None]:
    if not candidate_times:
        return None, None
    row, candidate_time = min(candidate_times, key=lambda item: abs((item[1] - gold_time).total_seconds()))
    return row, round((candidate_time - gold_time).total_seconds(), 3)


def proposal_center_wall_time(proposal: dict[str, Any]) -> datetime:
    return segment_filename_start(str(proposal["segment_path"])) + timedelta(seconds=float(proposal["center_offset_sec"]))


def segment_filename_start(path_text: str) -> datetime:
    start_key = Path(path_text).name.split("_", 1)[0]
    return datetime.strptime(start_key, "%Y%m%dT%H%M%S")


def _format_table(report: dict[str, Any]) -> str:
    lines = [
        f"Miner recall: {report['summary']['caught']}/{report['summary']['total_gold']} {report['verdict']}",
        "gold_id caught nearest_delta_sec nearest_candidate_id",
    ]
    for row in report["gold_results"]:
        lines.append(
            f"{row['id']} {str(row['caught']).lower()} "
            f"{row['nearest_delta_sec'] if row['nearest_delta_sec'] is not None else 'none'} "
            f"{row['nearest_candidate_id'] or 'none'}"
        )
    if report["verdict"] == "FAIL":
        lines.append(str(report["failure_next_step"]))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
