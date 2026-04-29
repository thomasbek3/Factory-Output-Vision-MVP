#!/usr/bin/env python3
"""Run targeted Factory2 diagnostic searches for unresolved proof-gap events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.diagnose_event_window import diagnose_event_window

DEFAULT_PLAN = Path("data/reports/factory2_final_gap_search_plan.v1.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_final_gap_search_run.v1.json")
DEFAULT_DIAGNOSTICS_ROOT = Path("data/diagnostics/event-windows")
DEFAULT_VIDEO = Path("data/videos/from-pc/factory2.MOV")
DEFAULT_CALIBRATION = Path("data/calibration/factory2_ai_only_v1.json")
DEFAULT_MODEL = Path("models/panel_in_transit.pt")
DEFAULT_PERSON_MODEL = Path("yolo11n.pt")
DEFAULT_CONFIDENCE = 0.20
DiagnosticRunner = Callable[..., dict[str, Any]]
SCHEMA_VERSION = "factory2-final-gap-search-run-v1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def diagnostic_slug(*, event_id: str, candidate_id: str, start_seconds: float, end_seconds: float, fps: float) -> str:
    suffix = event_id.split("-")[-1]
    return f"factory2-final-gap-search-{suffix}-{int(start_seconds):03d}-{int(end_seconds):03d}s-{int(round(fps))}fps-{candidate_id}"


def run_final_gap_search(
    *,
    plan_path: Path,
    output_path: Path,
    diagnostics_root: Path,
    video_path: Path,
    calibration_path: Path,
    model_path: Path,
    person_model_path: Path | None,
    diagnostic_runner: DiagnosticRunner = diagnose_event_window,
    candidate_limit_per_event: int | None,
    event_ids: set[str] | None,
    confidence: float = DEFAULT_CONFIDENCE,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if candidate_limit_per_event is not None and candidate_limit_per_event <= 0:
        raise ValueError("candidate_limit_per_event must be positive when provided")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []

    for target in plan.get("targets") or []:
        if not isinstance(target, dict):
            continue
        event_id = str(target.get("event_id") or "")
        if event_ids is not None and event_id not in event_ids:
            continue
        baseline_source_token_key = target.get("baseline_source_token_key")
        candidates = list(target.get("candidates") or [])
        if candidate_limit_per_event is not None:
            candidates = candidates[:candidate_limit_per_event]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            start_seconds = float(candidate.get("start_seconds") or 0.0)
            end_seconds = float(candidate.get("end_seconds") or 0.0)
            fps = float(candidate.get("fps") or 0.0)
            candidate_id = str(candidate.get("candidate_id") or "")
            slug = diagnostic_slug(
                event_id=event_id,
                candidate_id=candidate_id,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                fps=fps,
            )
            out_dir = diagnostics_root / slug
            diagnostic_result = diagnostic_runner(
                video_path=video_path,
                calibration_path=calibration_path,
                out_dir=out_dir,
                start_timestamp=start_seconds,
                end_timestamp=end_seconds,
                fps=fps,
                model_path=model_path,
                confidence=confidence,
                force=True,
                person_model_path=person_model_path,
            )
            diagnostic_path = out_dir / "diagnostic.json"
            if isinstance(diagnostic_result, dict):
                raw_path = diagnostic_result.get("diagnostic_path")
                if raw_path:
                    diagnostic_path = Path(raw_path)
            results.append(
                {
                    "event_id": event_id,
                    "event_ts": round(float(target.get("event_ts") or 0.0), 3),
                    "candidate_id": candidate_id,
                    "diagnostic_slug": slug,
                    "diagnostic_path": str(diagnostic_path),
                    "baseline_source_token_key": baseline_source_token_key,
                    "start_seconds": round(start_seconds, 3),
                    "end_seconds": round(end_seconds, 3),
                    "fps": fps,
                }
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "plan_path": str(plan_path),
        "result_count": len(results),
        "diagnostics_root": str(diagnostics_root),
        "results": results,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Factory2 final-gap diagnostic search plan")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--diagnostics-root", type=Path, default=DEFAULT_DIAGNOSTICS_ROOT)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--person-model", type=Path, default=DEFAULT_PERSON_MODEL)
    parser.add_argument("--event-id", action="append", dest="event_ids", default=None)
    parser.add_argument("--candidate-limit-per-event", type=int, default=None)
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_final_gap_search(
        plan_path=args.plan,
        output_path=args.output,
        diagnostics_root=args.diagnostics_root,
        video_path=args.video,
        calibration_path=args.calibration,
        model_path=args.model,
        person_model_path=args.person_model,
        candidate_limit_per_event=args.candidate_limit_per_event,
        event_ids=set(args.event_ids) if args.event_ids else None,
        confidence=args.confidence,
        force=args.force,
    )
    print(json.dumps({"result_count": payload["result_count"], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
