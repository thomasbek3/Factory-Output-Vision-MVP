#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.zone_tripwire import TripwireConfig, load_output_zone_polygon, run_tripwire_on_segment_manifest, run_tripwire_on_video

PASS_THRESHOLD = 6
DEFAULT_EXAM_CLIP_OFFSETS_SEC = [165.0, 510.0, 781.0, 1104.0, 1475.0, 1822.0, 2172.0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Day-5 tripwire recall against held-out positives.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tripwire-candidates", type=Path)
    source.add_argument("--video", type=Path)
    source.add_argument("--segment-manifest", type=Path)
    parser.add_argument("--gold-positives", type=Path, required=True, help="exam gold positives JSON")
    parser.add_argument("--pm-gold-positives", type=Path, help="Thomas PM 7 wall-clock labels text file")
    parser.add_argument("--gold-wall-date", default="2026-06-11", help="date for plain HH:MM:SS wall-clock labels")
    parser.add_argument("--station-calibration", type=Path)
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--trigger", choices=["person_presence", "pixel"], default="person_presence")
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--score-method", choices=["tiled_absdiff", "tiled_ssim", "tiled_edge"], default="tiled_absdiff")
    parser.add_argument("--burst-threshold", type=float, default=0.10)
    parser.add_argument("--state-threshold", type=float, default=0.06)
    parser.add_argument("--min-flash-ratio", type=float, default=1.5)
    parser.add_argument("--include-motion-burst", action="store_true")
    parser.add_argument("--person-conf", type=float, default=0.35)
    parser.add_argument("--person-model", default="yolov8m.pt")
    parser.add_argument("--presence-gap-sec", type=float, default=8.0)
    parser.add_argument("--episode-max-sec", type=float, default=60.0)
    parser.add_argument("--trigger-zone-margin", type=float, default=0.15)
    parser.add_argument("--episode-pad-sec", type=float, default=2.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.tripwire_candidates:
            tripwire_payload = json.loads(args.tripwire_candidates.read_text(encoding="utf-8"))
            mode = infer_candidate_time_mode(tripwire_payload)
        else:
            if args.station_calibration is None:
                raise ValueError("--station-calibration is required when running the tripwire")
            config = TripwireConfig(
                trigger=args.trigger,
                sample_fps=args.sample_fps,
                score_method=args.score_method,
                burst_threshold=args.burst_threshold,
                state_threshold=args.state_threshold,
                min_flash_ratio=args.min_flash_ratio,
                include_motion_burst=args.include_motion_burst,
                person_conf=args.person_conf,
                person_model=args.person_model,
                presence_gap_sec=args.presence_gap_sec,
                episode_max_sec=args.episode_max_sec,
                trigger_zone_margin=args.trigger_zone_margin,
                episode_pad_sec=args.episode_pad_sec,
            )
            polygon = load_output_zone_polygon(args.station_calibration)
            if args.video:
                tripwire_payload = run_tripwire_on_video(video_path=args.video, output_zone_polygon=polygon, config=config)
                mode = "clip_offsets"
            else:
                tripwire_payload = run_tripwire_on_segment_manifest(
                    segment_manifest_path=args.segment_manifest,
                    output_zone_polygon=polygon,
                    config=config,
                )
                mode = "wall_times"
        gold_payload = read_gold_payload(args.gold_positives, wall_date=args.gold_wall_date)
        if args.pm_gold_positives:
            pm_payload = read_gold_payload(args.pm_gold_positives, wall_date=args.gold_wall_date)
            report = build_multi_recall_report_from_payloads(
                tripwire_payload=tripwire_payload,
                recall_sets={
                    "exam": gold_payload,
                    "pm": pm_payload,
                },
                mode=mode,
                match_tolerance_sec=args.match_tolerance_sec,
            )
        else:
            report = build_recall_report_from_payloads(
                tripwire_payload=tripwire_payload,
                gold_payload=gold_payload,
                mode=mode,
                match_tolerance_sec=args.match_tolerance_sec,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(format_recall_table(report))
    return 0 if report["verdict"] == "PASS" else 1


def build_recall_report_from_payloads(
    *,
    tripwire_payload: dict[str, Any],
    gold_payload: dict[str, Any],
    mode: str,
    match_tolerance_sec: float,
) -> dict[str, Any]:
    if mode == "clip_offsets":
        gold = [{"id": row["id"], "time": row["time"]} for row in load_gold_clip_offsets(gold_payload)]
        candidates = candidate_clip_offsets(tripwire_payload.get("candidates") or [])
    elif mode == "wall_times":
        gold = [{"id": row["id"], "time": row["time"]} for row in load_gold_wall_times(gold_payload)]
        candidates = candidate_wall_times(tripwire_payload.get("candidates") or [])
    else:
        raise ValueError("mode must be clip_offsets or wall_times")
    return build_tripwire_recall_report(
        candidates=candidates,
        gold=gold,
        match_tolerance_sec=match_tolerance_sec,
        candidate_count=len(tripwire_payload.get("candidates") or []),
    )


def build_multi_recall_report_from_payloads(
    *,
    tripwire_payload: dict[str, Any],
    recall_sets: dict[str, dict[str, Any]],
    mode: str,
    match_tolerance_sec: float,
) -> dict[str, Any]:
    reports = {
        name: build_recall_report_from_payloads(
            tripwire_payload=tripwire_payload,
            gold_payload=gold_payload,
            mode=mode,
            match_tolerance_sec=match_tolerance_sec,
        )
        for name, gold_payload in recall_sets.items()
    }
    verdict = "PASS" if all(report["verdict"] == "PASS" for report in reports.values()) else "FAIL"
    return {
        "schema_version": "factory-vision-tripwire-recall-gate-v2",
        "verdict": verdict,
        "pass_threshold": PASS_THRESHOLD,
        "candidate_counts": candidate_count_summary(tripwire_payload),
        "recall_sets": reports,
    }


def build_tripwire_recall_report(
    *,
    candidates: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    match_tolerance_sec: float,
    candidate_count: int | None = None,
) -> dict[str, Any]:
    rows = []
    caught_count = 0
    for gold_row in gold:
        nearest = nearest_candidate(gold_row["time"], candidates)
        delta = None if nearest is None else _time_delta_seconds(nearest["time"], gold_row["time"])
        caught = delta is not None and abs(delta) <= match_tolerance_sec
        if caught:
            caught_count += 1
        rows.append(
            {
                "id": gold_row["id"],
                "caught": caught,
                "nearest_candidate_id": None if nearest is None else nearest.get("candidate_id"),
                "nearest_delta_sec": None if delta is None else round(delta, 3),
            }
        )
    verdict = "PASS" if caught_count >= PASS_THRESHOLD else "FAIL"
    return {
        "schema_version": "factory-vision-tripwire-recall-gate-v1",
        "verdict": verdict,
        "pass_threshold": PASS_THRESHOLD,
        "summary": {
            "caught": caught_count,
            "total_gold": len(gold),
            "candidate_count": len(candidates) if candidate_count is None else candidate_count,
        },
        "gold_results": rows,
    }


def read_gold_payload(path: Path, *, wall_date: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    events = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        events.append({"id": f"pm-gold-{len(events) + 1:02d}", "wall_clock": stripped})
    if not events:
        raise ValueError(f"gold positives file has no usable rows: {path}")
    return {
        "schema": "plain_wall_clock_times_v1",
        "source": str(path),
        "wall_date": wall_date,
        "events": events,
    }


def infer_candidate_time_mode(tripwire_payload: dict[str, Any]) -> str:
    candidates = tripwire_payload.get("candidates") or []
    if any(candidate.get("segment_path") or candidate.get("segment_id") for candidate in candidates):
        return "wall_times"
    return "clip_offsets"


def candidate_count_summary(tripwire_payload: dict[str, Any]) -> dict[str, Any]:
    summary = tripwire_payload.get("summary") or {}
    after = int(summary.get("candidate_count_after_dedup", summary.get("candidate_count", 0)))
    before = int(summary.get("candidate_count_before_dedup", summary.get("raw_pixel_candidate_count", after)))
    return {
        "before_dedup": before,
        "after_dedup": after,
        "raw_pixel_candidate_count": int(summary.get("raw_pixel_candidate_count", before)),
        "person_visit_count": int(summary.get("person_visit_count", 0)),
        "quiet_state_diff_count": int(summary.get("quiet_state_diff_count", 0)),
        "motion_burst_count": int(summary.get("motion_burst_count", 0)),
    }


def load_gold_clip_offsets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("events") or []
    loaded = []
    for index, row in enumerate(rows):
        if "clip_offset_sec" in row:
            loaded.append({"id": row.get("id", f"gold-{index + 1:02d}"), "time": float(row["clip_offset_sec"])})
        elif "offset_sec" in row:
            loaded.append({"id": row.get("id", f"gold-{index + 1:02d}"), "time": float(row["offset_sec"])})
    if loaded:
        return loaded
    if payload.get("schema") == "exam_gold_positives_v1" and len(rows) == 7:
        return [
            {"id": rows[index].get("id", f"exam-gold-{index + 1:02d}"), "time": offset}
            for index, offset in enumerate(DEFAULT_EXAM_CLIP_OFFSETS_SEC)
        ]
    raise ValueError("gold positives do not include clip offsets")


def load_gold_wall_times(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema") == "plain_wall_clock_times_v1":
        wall_date = str(payload.get("wall_date") or "")
        if not wall_date:
            raise ValueError("plain wall-clock labels require wall_date")
        rows = []
        for index, row in enumerate(payload.get("events") or []):
            wall_clock = str(row.get("wall_clock", "")).strip()
            if not wall_clock:
                continue
            rows.append(
                {
                    "id": row.get("id", f"gold-{index + 1:02d}"),
                    "time": datetime.strptime(f"{wall_date}T{wall_clock}", "%Y-%m-%dT%H:%M:%S"),
                }
            )
        if rows:
            return rows
        raise ValueError("plain wall-clock labels do not include wall_clock rows")

    rows = []
    for index, row in enumerate(payload.get("events") or []):
        if "segment_file" not in row or "offset_in_segment_sec" not in row:
            continue
        rows.append(
            {
                "id": row.get("id", f"gold-{index + 1:02d}"),
                "time": segment_filename_start(str(row["segment_file"])) + timedelta(seconds=float(row["offset_in_segment_sec"])),
            }
        )
    if not rows:
        raise ValueError("gold positives do not include segment wall times")
    return rows


def candidate_clip_offsets(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, candidate in enumerate(candidates):
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id", f"candidate-{index + 1:05d}"),
                "time": float(candidate.get("center_sec", candidate.get("center_offset_sec", 0.0))),
            }
        )
    return rows


def candidate_wall_times(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, candidate in enumerate(candidates):
        segment_path = candidate.get("segment_path") or candidate.get("source")
        if not segment_path:
            continue
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id", f"candidate-{index + 1:05d}"),
                "time": segment_filename_start(str(segment_path))
                + timedelta(seconds=float(candidate.get("center_offset_sec", candidate.get("center_sec", 0.0)))),
            }
        )
    return rows


def nearest_candidate(gold_time: Any, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs(_time_delta_seconds(row["time"], gold_time)))


def segment_filename_start(path_text: str) -> datetime:
    start_key = Path(path_text).name.split("_", 1)[0]
    return datetime.strptime(start_key, "%Y%m%dT%H%M%S")


def _time_delta_seconds(candidate_time: Any, gold_time: Any) -> float:
    if isinstance(candidate_time, datetime) and isinstance(gold_time, datetime):
        return (candidate_time - gold_time).total_seconds()
    return float(candidate_time) - float(gold_time)


def format_recall_table(report: dict[str, Any]) -> str:
    if "recall_sets" in report:
        counts = report.get("candidate_counts") or {}
        lines = [
            f"Candidate count before dedup: {counts.get('before_dedup')}",
            f"Candidate count after dedup: {counts.get('after_dedup')}",
        ]
        for name, subreport in report["recall_sets"].items():
            title = name.upper() if name == "pm" else name.title()
            lines.append(
                f"{title} tripwire recall: {subreport['summary']['caught']}/{subreport['summary']['total_gold']} {subreport['verdict']}"
            )
            lines.append(f"{title} gold_id caught nearest_delta_sec nearest_candidate_id")
            for row in subreport["gold_results"]:
                lines.append(
                    f"{title} {row['id']} {str(row['caught']).lower()} {row['nearest_delta_sec']} {row['nearest_candidate_id']}"
                )
        lines.append(f"Overall verdict: {report['verdict']}")
        return "\n".join(lines)

    lines = [
        f"Tripwire recall: {report['summary']['caught']}/{report['summary']['total_gold']} {report['verdict']}",
        "gold_id caught nearest_delta_sec nearest_candidate_id",
    ]
    for row in report["gold_results"]:
        lines.append(
            f"{row['id']} {str(row['caught']).lower()} {row['nearest_delta_sec']} {row['nearest_candidate_id']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
