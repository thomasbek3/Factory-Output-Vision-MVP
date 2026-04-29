#!/usr/bin/env python3
"""Audit one-pass runtime count events on factory2-style videos."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Iterator

import cv2

from app.core.settings import get_event_track_max_match_distance, get_person_conf_threshold
from app.services.count_state_machine import CountEvent
from app.services.counting import YoloObjectDetector
from app.services.person_detector import PersonDetector
from app.services.runtime_event_counter import RuntimeEventCounter, load_runtime_calibration

SCHEMA_VERSION = "factory2-runtime-event-audit-v1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sampled_frame_indices(
    *,
    video_fps: float,
    frame_count: int,
    processing_fps: float,
    start_seconds: float,
    end_seconds: float | None,
) -> Iterator[int]:
    fps = max(float(video_fps), 1.0)
    step = max(int(round(fps / max(float(processing_fps), 0.1))), 1)
    start_frame = max(int(start_seconds * fps), 0)
    limit_frame = frame_count if end_seconds is None else min(frame_count, int(end_seconds * fps))
    for index in range(start_frame, max(limit_frame, start_frame), step):
        yield index


def serialize_event(
    *,
    event_ts: float,
    event: CountEvent,
    gate_decision: Any,
    count_total: int,
) -> dict[str, Any]:
    return {
        "event_ts": round(float(event_ts), 3),
        "track_id": int(event.track_id),
        "reason": event.reason,
        "count_total": int(count_total),
        "bbox": [round(float(value), 3) for value in event.bbox],
        "gate_decision": None
        if gate_decision is None
        else {
            "decision": gate_decision.decision,
            "reason": gate_decision.reason,
            "flags": list(gate_decision.flags),
        },
    }


def audit_runtime_events(
    *,
    video_path: Path,
    calibration_path: Path,
    model_path: Path,
    output_path: Path,
    start_seconds: float,
    end_seconds: float | None,
    processing_fps: float,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not calibration_path.exists():
        raise FileNotFoundError(calibration_path)
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    zones, gate = load_runtime_calibration(calibration_path)
    counter = RuntimeEventCounter(
        zones=zones,
        gate=gate,
        tracker_match_distance=get_event_track_max_match_distance(),
    )
    detector = YoloObjectDetector(model_path=str(model_path), conf_threshold=0.25, excluded_classes=[])
    person = PersonDetector(get_person_conf_threshold())

    capture = cv2.VideoCapture(str(video_path))
    video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_indices = list(
        sampled_frame_indices(
            video_fps=video_fps,
            frame_count=frame_count,
            processing_fps=processing_fps,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
    )

    started = time.time()
    last_index = -1
    events: list[dict[str, Any]] = []
    for index in frame_indices:
        if last_index < 0 or index != last_index + 1:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        last_index = index
        timestamp = index / max(video_fps, 1.0)
        detection_result = detector.detect(frame)
        detections = [{"box": item.bbox, "confidence": 1.0} for item in detection_result.detections]
        person_boxes = [(item.x, item.y, item.w, item.h) for item in person.detect_people(frame)]
        frame_result = counter.process_frame(frame=frame, detections=detections, person_boxes=person_boxes)
        for event in frame_result.events:
            events.append(
                serialize_event(
                    event_ts=timestamp,
                    event=event,
                    gate_decision=frame_result.gate_decisions.get(event.track_id),
                    count_total=counter.total_count,
                )
            )

    capture.release()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "video_path": str(video_path),
        "calibration_path": str(calibration_path),
        "model_path": str(model_path),
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "processing_fps": processing_fps,
        "video_fps": video_fps,
        "sampled_frame_count": len(frame_indices),
        "final_count": counter.total_count,
        "elapsed_sec": round(time.time() - started, 3),
        "events": events,
    }
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit one-pass runtime events on factory2-style videos")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-seconds", type=float, default=0.0)
    parser.add_argument("--end-seconds", type=float, default=None)
    parser.add_argument("--processing-fps", type=float, default=10.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = audit_runtime_events(
        video_path=args.video,
        calibration_path=args.calibration,
        model_path=args.model,
        output_path=args.output,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        processing_fps=args.processing_fps,
        force=args.force,
    )
    print(json.dumps({"final_count": payload["final_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
