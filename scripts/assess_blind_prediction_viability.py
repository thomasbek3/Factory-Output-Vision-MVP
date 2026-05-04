#!/usr/bin/env python3
"""Assess whether detector evidence supports a numeric blind prediction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TRANSFER_FAILED = "transfer_failed_build_video_specific_detector"
STATIC_RISK = "broad_or_static_detector_risk_requires_runtime_diagnostic"
PLAUSIBLE_TRANSFER = "plausible_transfer_candidate_run_fast_diagnostic"
EOF_EVENT_REASON = "end_of_stream_active_track_event"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normal_model_name(model_path: str) -> str:
    return Path(model_path).name


def summarize_transfer_screen(
    screen: dict[str, Any],
    *,
    static_risk_models: set[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    active_rows: list[dict[str, Any]] = []
    static_rows: list[dict[str, Any]] = []

    for model in screen.get("models", []):
        model_path = str(model.get("model_path", ""))
        model_names = {model_path, _normal_model_name(model_path)}
        configured_static = bool(model_names & static_risk_models)
        for summary in model.get("confidence_summaries", []):
            row = {
                "model_path": model_path,
                "confidence": summary.get("confidence"),
                "images_with_detections": summary.get("images_with_detections", 0),
                "sample_count": summary.get("sample_count", screen.get("sample_count", 0)),
                "detection_rate": summary.get("detection_rate", 0.0),
                "total_detections": summary.get("total_detections", 0),
                "recommendation": summary.get("recommendation"),
                "configured_static_risk_model": configured_static,
            }
            rows.append(row)
            if configured_static or row["recommendation"] == STATIC_RISK:
                static_rows.append(row)
            else:
                active_rows.append(row)

    active_plausible = any(row["recommendation"] == PLAUSIBLE_TRANSFER for row in active_rows)
    active_failed = bool(active_rows) and all(row["recommendation"] == TRANSFER_FAILED for row in active_rows)
    static_detector_risk = bool(static_rows)
    return {
        "active_transfer_failed": active_failed,
        "active_transfer_plausible": active_plausible,
        "static_detector_risk": static_detector_risk,
        "active_rows": active_rows,
        "static_rows": static_rows,
        "rows": rows,
    }


def summarize_runtime_diagnostic(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events", [])
    eof_events = [event for event in events if event.get("reason") == EOF_EVENT_REASON]
    non_eof_events = [event for event in events if event.get("reason") != EOF_EVENT_REASON]
    tiny_travel_events = [
        event
        for event in non_eof_events
        if event.get("travel_px") is not None and float(event["travel_px"]) <= 5.0
    ]
    event_timestamps = [
        float(event["event_ts"])
        for event in non_eof_events
        if event.get("event_ts") is not None
    ]
    return {
        "path": path.as_posix(),
        "current_state": payload.get("current_state"),
        "observed_event_count": payload.get("observed_event_count", len(events)),
        "raw_event_count": len(events),
        "non_eof_event_count": len(non_eof_events),
        "eof_event_count": len(eof_events),
        "tiny_travel_event_count": len(tiny_travel_events),
        "first_non_eof_event_ts": min(event_timestamps) if event_timestamps else None,
        "last_non_eof_event_ts": max(event_timestamps) if event_timestamps else None,
    }


def summarize_runtime_diagnostics(diagnostic_payloads: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    summaries = [
        summarize_runtime_diagnostic(path, payload)
        for path, payload in diagnostic_payloads
    ]
    counts = [summary["non_eof_event_count"] for summary in summaries]
    count_spread = max(counts) - min(counts) if counts else 0
    return {
        "summaries": summaries,
        "non_eof_event_count_spread": count_spread,
        "parameter_sensitive": count_spread > 0,
    }


def assess_viability(
    *,
    detector_screen: dict[str, Any],
    detector_screen_path: Path,
    diagnostic_payloads: list[tuple[Path, dict[str, Any]]],
    static_risk_models: set[str],
) -> dict[str, Any]:
    transfer_summary = summarize_transfer_screen(
        detector_screen,
        static_risk_models=static_risk_models,
    )
    runtime_summary = summarize_runtime_diagnostics(diagnostic_payloads)
    reasons: list[str] = []

    if transfer_summary["active_transfer_plausible"]:
        status = "plausible_prediction_path_available"
        numeric_prediction_allowed = True
        reasons.append("At least one non-static detector has a plausible transfer screen.")
    elif transfer_summary["active_transfer_failed"] and transfer_summary["static_detector_risk"] and diagnostic_payloads:
        status = "no_valid_blind_prediction"
        numeric_prediction_allowed = False
        reasons.append("All non-static transferred detectors failed or were near-dead.")
        reasons.append("The only high-recall path is a configured/static detector risk.")
        reasons.append("Runtime diagnostic events are evidence for hard negatives, not a valid blind count.")
        if runtime_summary["parameter_sensitive"]:
            reasons.append("Runtime diagnostic counts changed across settings, so the output is parameter-sensitive.")
    elif transfer_summary["active_transfer_failed"]:
        status = "needs_video_specific_detector_before_prediction"
        numeric_prediction_allowed = False
        reasons.append("Non-static transferred detectors failed; build or label for a video-specific detector first.")
    else:
        status = "needs_review_before_prediction"
        numeric_prediction_allowed = False
        reasons.append("Detector screen did not establish a plausible numeric prediction path.")

    return {
        "schema_version": "factory-vision-blind-prediction-viability-v1",
        "detector_screen_path": detector_screen_path.as_posix(),
        "diagnostic_paths": [path.as_posix() for path, _payload in diagnostic_payloads],
        "status": status,
        "numeric_prediction_allowed": numeric_prediction_allowed,
        "reasons": reasons,
        "static_risk_models": sorted(static_risk_models),
        "transfer_summary": transfer_summary,
        "runtime_diagnostics": runtime_summary,
        "recommendation": (
            "route_to_learning_library"
            if not numeric_prediction_allowed
            else "continue_with_plausible_runtime_diagnostic"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess whether detector transfer and runtime diagnostics support a blind numeric prediction"
    )
    parser.add_argument("--detector-screen", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, action="append", default=[])
    parser.add_argument(
        "--static-risk-model",
        action="append",
        default=["models/wire_mesh_panel.pt", "wire_mesh_panel.pt"],
        help="Model path or basename that should be treated as static-detector risk.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    detector_screen = read_json(args.detector_screen)
    diagnostics = [(path, read_json(path)) for path in args.diagnostic]
    payload = assess_viability(
        detector_screen=detector_screen,
        detector_screen_path=args.detector_screen,
        diagnostic_payloads=diagnostics,
        static_risk_models=set(args.static_risk_model),
    )
    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": args.output.as_posix(), "status": payload["status"]}))


if __name__ == "__main__":
    main()
