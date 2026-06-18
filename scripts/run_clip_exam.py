#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.placement_counter import PlacementVerdict, count_placements
from app.services.zone_tripwire import TripwireConfig, load_output_zone_polygon, run_tripwire_on_video
from scripts.validate_tripwire_recall import DEFAULT_EXAM_CLIP_OFFSETS_SEC, load_gold_clip_offsets

StudentJudge = Callable[[dict[str, Any]], dict[str, Any]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Day-4 tripwire -> clip student -> debounce blind exam.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--gold-positives", type=Path, required=True)
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--arch", choices=["stack3_mobilenet", "video_x3d", "video_vmae", "twostream"], required=True)
    parser.add_argument("--debounce-sec", type=float, default=25.0)
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        result = run_clip_exam(
            video_path=args.video,
            gold_positives_path=args.gold_positives,
            station_calibration_path=args.station_calibration,
            model_path=args.model,
            arch=args.arch,
            debounce_sec=args.debounce_sec,
            match_tolerance_sec=args.match_tolerance_sec,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def run_clip_exam(
    *,
    video_path: Path,
    gold_positives_path: Path,
    station_calibration_path: Path,
    model_path: Path,
    arch: str,
    debounce_sec: float,
    match_tolerance_sec: float,
) -> dict[str, Any]:
    from app.services.clip_models import load_student_judge

    tripwire_payload = run_tripwire_on_video(
        video_path=video_path,
        output_zone_polygon=load_output_zone_polygon(station_calibration_path),
        config=TripwireConfig(),
    )
    judge = load_student_judge(model_path=model_path, arch=arch)
    gold_payload = json.loads(gold_positives_path.read_text(encoding="utf-8"))
    gold_offsets = [row["time"] for row in load_gold_clip_offsets(gold_payload)]
    return run_exam_from_candidates(
        candidates=tripwire_payload.get("candidates") or [],
        gold_offsets=gold_offsets,
        judge=judge,
        debounce_sec=debounce_sec,
        match_tolerance_sec=match_tolerance_sec,
        model_name=arch,
    )


def run_exam_from_candidates(
    *,
    candidates: list[dict[str, Any]],
    gold_offsets: list[float] | None = None,
    judge: StudentJudge,
    debounce_sec: float = 25.0,
    match_tolerance_sec: float = 20.0,
    model_name: str = "student",
) -> dict[str, Any]:
    gold_offsets = gold_offsets or list(DEFAULT_EXAM_CLIP_OFFSETS_SEC)
    verdicts = []
    for candidate in sorted(candidates, key=lambda row: float(row.get("center_sec", 0.0))):
        judged = judge(candidate)
        decision = str(judged.get("decision", "refute"))
        verdicts.append(
            PlacementVerdict(
                center_sec=float(candidate.get("center_sec", candidate.get("center_offset_sec", 0.0))),
                decision="assert" if decision == "assert" else "refute",
                score=float(judged.get("score", 0.0)),
                candidate_id=str(candidate.get("candidate_id", "")),
            )
        )
    events = count_placements(verdicts, debounce_sec=debounce_sec)
    count_times = [event.center_sec for event in events]
    score = score_counts_against_gold(
        count_times=count_times,
        gold_times=gold_offsets,
        match_tolerance_sec=match_tolerance_sec,
    )
    return {
        "schema_version": "factory-vision-clip-exam-v1",
        "model": model_name,
        "candidate_count": len(candidates),
        "count_times": [round(value, 3) for value in count_times],
        "matched": score["matched"],
        "missed": score["missed"],
        "false_counts": score["false_counts"],
        "passed": score["passed"],
        "matches": score["matches"],
    }


def score_counts_against_gold(
    *,
    count_times: list[float],
    gold_times: list[float],
    match_tolerance_sec: float,
) -> dict[str, Any]:
    unmatched_counts = set(range(len(count_times)))
    matches = []
    for gold_index, gold_time in enumerate(gold_times):
        best_index = None
        best_delta = None
        for count_index in unmatched_counts:
            delta = float(count_times[count_index]) - float(gold_time)
            if best_delta is None or abs(delta) < abs(best_delta):
                best_delta = delta
                best_index = count_index
        if best_index is not None and best_delta is not None and abs(best_delta) <= match_tolerance_sec:
            unmatched_counts.remove(best_index)
            matches.append(
                {
                    "gold_index": gold_index,
                    "gold_sec": round(float(gold_time), 3),
                    "count_sec": round(float(count_times[best_index]), 3),
                    "delta_sec": round(best_delta, 3),
                }
            )
    matched = len(matches)
    missed = len(gold_times) - matched
    false_counts = len(unmatched_counts)
    return {
        "matched": matched,
        "missed": missed,
        "false_counts": false_counts,
        "passed": matched == len(gold_times) and false_counts == 0,
        "matches": matches,
    }


if __name__ == "__main__":
    raise SystemExit(main())
