"""Blind exam kernel: candidates -> verdicts -> debounced counts -> gold matching.

Extracted from scripts/run_clip_exam.py so the live runtime, tests, and the CLI
all share one importable implementation of the Track B promotion gate
(ADR-0004). The CLI in scripts/run_clip_exam.py is a thin shell over this
module; nothing here may import from scripts.* (app -> scripts layering is
inverted by design).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from app.services.placement_counter import PlacementVerdict, count_placements

StudentJudge = Callable[[dict[str, Any]], dict[str, Any]]

LOGGER = logging.getLogger(__name__)

# Gold offsets for the seven-placement blind exam hour. Owned here; the recall
# validator re-exports for backwards compatibility.
DEFAULT_EXAM_CLIP_OFFSETS_SEC = [165.0, 510.0, 781.0, 1104.0, 1475.0, 1822.0, 2172.0]

EXAM_RESULT_SCHEMA_VERSION = "factory-vision-clip-exam-v1"


def load_gold_clip_offsets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read gold positive rows from an exam-gold payload.

    Accepts explicit clip_offset_sec/offset_sec rows; falls back to the default
    seven-offset exam layout when the payload declares exam_gold_positives_v1
    with exactly seven events and no explicit offsets.
    """
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


def split_edge_truncated_candidates(
    *,
    candidates: list[dict[str, Any]],
    duration_sec: float,
    bracket_sec: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate candidates whose clip window would be truncated at a video edge.

    Truncated windows cannot contain a full bracketed placement, so they are
    returned as refutes without spending a judge call.
    """
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


def score_counts_against_gold(
    *,
    count_times: list[float],
    gold_times: list[float],
    match_tolerance_sec: float,
) -> dict[str, Any]:
    """Greedy nearest-match scoring of runtime counts against gold positives."""
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
    """Judge candidates, debounce into counts, and score against gold."""
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
        "schema_version": EXAM_RESULT_SCHEMA_VERSION,
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
