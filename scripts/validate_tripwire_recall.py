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
    parser = argparse.ArgumentParser(description="Validate Day-4 Tripwire v2 recall against held-out exam positives.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tripwire-candidates", type=Path)
    source.add_argument("--video", type=Path)
    source.add_argument("--segment-manifest", type=Path)
    parser.add_argument("--gold-positives", type=Path, required=True)
    parser.add_argument("--station-calibration", type=Path)
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--score-method", choices=["tiled_absdiff", "tiled_ssim", "tiled_edge"], default="tiled_absdiff")
    parser.add_argument("--burst-threshold", type=float, default=0.10)
    parser.add_argument("--state-threshold", type=float, default=0.06)
    parser.add_argument("--min-flash-ratio", type=float, default=1.5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.tripwire_candidates:
            tripwire_payload = json.loads(args.tripwire_candidates.read_text(encoding="utf-8"))
            mode = "clip_offsets"
        else:
            if args.station_calibration is None:
                raise ValueError("--station-calibration is required when running the tripwire")
            config = TripwireConfig(
                sample_fps=args.sample_fps,
                score_method=args.score_method,
                burst_threshold=args.burst_threshold,
                state_threshold=args.state_threshold,
                min_flash_ratio=args.min_flash_ratio,
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
        gold_payload = json.loads(args.gold_positives.read_text(encoding="utf-8"))
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
