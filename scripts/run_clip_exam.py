#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.placement_counter import PlacementVerdict, count_placements
from app.services.zone_tripwire import TripwireConfig, load_output_zone_polygon, run_tripwire_on_video, write_tripwire_payload
from scripts.validate_tripwire_recall import DEFAULT_EXAM_CLIP_OFFSETS_SEC, load_gold_clip_offsets

StudentJudge = Callable[[dict[str, Any]], dict[str, Any]]
LOGGER = logging.getLogger(__name__)
TRIPWIRE_CANDIDATES_SCHEMA = "tripwire-candidates-v1"
STAGE_EXIT_CODES = {"tripwire": 20, "candidates": 24, "extract": 21, "judge": 22, "count": 23}


@dataclass
class StageFailure(Exception):
    stage: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Day-4 tripwire -> clip student -> debounce blind exam.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--gold-positives", type=Path, required=True)
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--arch", choices=["stack3_mobilenet", "video_x3d", "video_vmae", "twostream"])
    parser.add_argument("--clip-cache-dir", type=Path)
    parser.add_argument("--write-candidates", type=Path)
    parser.add_argument("--candidates", type=Path)
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
            clip_cache_dir=args.clip_cache_dir or args.out.parent / "clip_cache",
            arch=args.arch,
            debounce_sec=args.debounce_sec,
            match_tolerance_sec=args.match_tolerance_sec,
            write_candidates_path=args.write_candidates,
            candidates_path=args.candidates,
        )
    except StageFailure as exc:
        print(f"{exc.stage} stage failed", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        return STAGE_EXIT_CODES[exc.stage]
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
    clip_cache_dir: Path,
    arch: str | None,
    debounce_sec: float,
    match_tolerance_sec: float,
    write_candidates_path: Path | None = None,
    candidates_path: Path | None = None,
) -> dict[str, Any]:
    from app.services.clip_dataset import extract_clip_dataset
    from app.services.clip_models import encodings_for_arch, load_student_judge, resolve_student_arch

    resolved_arch = _run_stage("judge", lambda: resolve_student_arch(model_path=model_path, fallback_arch=arch))
    output_zone_polygon = _run_stage("tripwire", lambda: load_output_zone_polygon(station_calibration_path))
    config = TripwireConfig()
    if candidates_path is not None:
        tripwire_payload = _run_stage("candidates", lambda: load_tripwire_candidates_payload(candidates_path))
    else:
        tripwire_payload = _run_stage(
            "tripwire",
            lambda: run_tripwire_on_video(
                video_path=video_path,
                output_zone_polygon=output_zone_polygon,
                config=config,
            ),
        )
        if write_candidates_path is not None:
            _run_stage(
                "candidates",
                lambda: write_tripwire_candidates_payload(write_candidates_path, tripwire_payload),
            )
    candidates = tripwire_payload.get("candidates") or []
    ready_candidates, edge_refutes = split_edge_truncated_candidates(
        candidates=candidates,
        duration_sec=float((tripwire_payload.get("summary") or {}).get("duration_sec", 0.0)),
        bracket_sec=config.bracket_sec,
    )
    extracted = _run_stage(
        "extract",
        lambda: extract_clip_dataset(
            candidates=ready_candidates,
            output_dir=clip_cache_dir,
            output_zone_polygon=output_zone_polygon,
            default_video_path=video_path,
            encoding=encodings_for_arch(resolved_arch),
        ),
    )
    judge = _run_stage("judge", lambda: load_student_judge(model_path=model_path, arch=resolved_arch))
    gold_payload = _run_stage("count", lambda: json.loads(gold_positives_path.read_text(encoding="utf-8")))
    gold_offsets = _run_stage("count", lambda: [row["time"] for row in load_gold_clip_offsets(gold_payload)])
    return _run_stage(
        "count",
        lambda: run_exam_from_candidates(
            candidates=[*extracted.get("samples", []), *edge_refutes],
            gold_offsets=gold_offsets,
            judge=judge,
            debounce_sec=debounce_sec,
            match_tolerance_sec=match_tolerance_sec,
            model_name=resolved_arch,
            finalize_at_end=True,
        ),
    )


def _run_stage(stage: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        raise StageFailure(stage) from exc


def write_tripwire_candidates_payload(path: Path, payload: dict[str, Any]) -> None:
    cached_payload = dict(payload)
    cached_payload["schema"] = TRIPWIRE_CANDIDATES_SCHEMA
    write_tripwire_payload(path, cached_payload)


def load_tripwire_candidates_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema")
    if schema != TRIPWIRE_CANDIDATES_SCHEMA:
        raise ValueError(f"candidates schema must be {TRIPWIRE_CANDIDATES_SCHEMA!r}; got {schema!r}")
    return payload


def split_edge_truncated_candidates(
    *,
    candidates: list[dict[str, Any]],
    duration_sec: float,
    bracket_sec: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready: list[dict[str, Any]] = []
    refutes: list[dict[str, Any]] = []
    expected_span = bracket_sec * 2.0
    for candidate in candidates:
        start_sec = float(candidate.get("start_sec", candidate.get("start_offset_sec", 0.0)))
        end_sec = float(candidate.get("end_sec", candidate.get("end_offset_sec", start_sec)))
        touches_edge = start_sec <= 0.0 or (duration_sec > 0 and end_sec >= duration_sec)
        if touches_edge and end_sec - start_sec < expected_span - 1e-6:
            candidate_id = str(candidate.get("candidate_id", ""))
            reason = "clip window truncated at video edge"
            LOGGER.warning("%s judged refute: %s", candidate_id or "<unknown>", reason)
            refute = dict(candidate)
            refute["skip_judge_reason"] = reason
            refutes.append(refute)
            continue
        ready.append(candidate)
    return ready, refutes


def run_exam_from_candidates(
    *,
    candidates: list[dict[str, Any]],
    gold_offsets: list[float] | None = None,
    judge: StudentJudge,
    debounce_sec: float = 25.0,
    match_tolerance_sec: float = 20.0,
    model_name: str = "student",
    finalize_at_end: bool = False,
) -> dict[str, Any]:
    gold_offsets = gold_offsets or list(DEFAULT_EXAM_CLIP_OFFSETS_SEC)
    verdicts = []
    for candidate in sorted(candidates, key=lambda row: float(row.get("center_sec", 0.0))):
        if candidate.get("skip_judge_reason"):
            judged = {"decision": "refute", "score": 0.0}
        else:
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
    events = count_placements(verdicts, debounce_sec=debounce_sec, finalize_at_end=finalize_at_end)
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
        "counts": [
            {
                "count": event.count,
                "center_sec": round(event.center_sec, 3),
                "start_sec": round(event.start_sec, 3),
                "end_sec": round(event.end_sec, 3),
                "candidate_ids": event.candidate_ids,
            }
            for event in events
        ],
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
