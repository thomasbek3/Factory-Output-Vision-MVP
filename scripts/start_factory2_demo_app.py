#!/usr/bin/env python3
"""Launch the verified Factory2 investor demo app configuration."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


DEFAULT_VIDEO_PATH = Path("data/videos/from-pc/factory2.MOV")
DEFAULT_CALIBRATION_PATH = Path("data/calibration/factory2_ai_only_v1.json")


def _stringify_number(value: float) -> str:
    return f"{value:g}"


def build_demo_env(
    *,
    base_env: dict[str, str] | None = None,
    video_path: Path = DEFAULT_VIDEO_PATH,
    calibration_path: Path | None = DEFAULT_CALIBRATION_PATH,
    model_path: Path | None = None,
    yolo_confidence: float | None = None,
    event_track_max_age: int | None = None,
    event_track_min_frames: int | None = None,
    event_track_min_travel_px: float | None = None,
    event_count_debounce_sec: float | None = None,
    event_track_max_match_distance: float | None = None,
    event_detection_cluster_distance: float | None = None,
    playback_speed: float = 1.0,
    processing_fps: float = 10.0,
    reader_fps: float = 10.0,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update(
        {
            "FC_DEMO_MODE": "1",
            "FC_DEMO_VIDEO_PATH": str(video_path.resolve()),
            "FC_DEMO_LOOP": "0",
            "FC_DEMO_PLAYBACK_SPEED": _stringify_number(playback_speed),
            "FC_DEMO_COUNT_MODE": "live_reader_snapshot",
            "FC_COUNTING_MODE": "event_based",
            "FC_RUNTIME_CALIBRATION_PATH": "" if calibration_path is None else str(calibration_path.resolve()),
            "FC_PROCESSING_FPS": _stringify_number(processing_fps),
            "FC_READER_FPS": _stringify_number(reader_fps),
        }
    )
    if model_path is not None:
        env["FC_YOLO_MODEL_PATH"] = str(model_path.resolve())
        env.setdefault("FC_YOLO_EXCLUDED_CLASSES", "")
    if yolo_confidence is not None:
        env["FC_YOLO_CONF_THRESHOLD"] = _stringify_number(yolo_confidence)
    if event_track_max_age is not None:
        env["FC_EVENT_TRACK_MAX_AGE"] = str(event_track_max_age)
    if event_track_min_frames is not None:
        env["FC_EVENT_TRACK_MIN_FRAMES"] = str(event_track_min_frames)
    if event_track_min_travel_px is not None:
        env["FC_EVENT_TRACK_MIN_TRAVEL_PX"] = _stringify_number(event_track_min_travel_px)
    if event_count_debounce_sec is not None:
        env["FC_EVENT_COUNT_DEBOUNCE_SEC"] = _stringify_number(event_count_debounce_sec)
    if event_track_max_match_distance is not None:
        env["FC_EVENT_TRACK_MAX_MATCH_DISTANCE"] = _stringify_number(event_track_max_match_distance)
    if event_detection_cluster_distance is not None:
        env["FC_EVENT_DETECTION_CLUSTER_DISTANCE"] = _stringify_number(event_detection_cluster_distance)
    return env


def build_uvicorn_command(*, port: int, python_executable: str | None = None) -> list[str]:
    return [
        python_executable or sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the verified Factory2 investor demo app")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_PATH)
    parser.add_argument("--no-runtime-calibration", action="store_true")
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--yolo-confidence", type=float, default=None)
    parser.add_argument("--event-track-max-age", type=int, default=None)
    parser.add_argument("--event-track-min-frames", type=int, default=None)
    parser.add_argument("--event-track-min-travel-px", type=float, default=None)
    parser.add_argument("--event-count-debounce-sec", type=float, default=None)
    parser.add_argument("--event-track-max-match-distance", type=float, default=None)
    parser.add_argument("--event-detection-cluster-distance", type=float, default=None)
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument("--processing-fps", type=float, default=10.0)
    parser.add_argument("--reader-fps", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = build_demo_env(
        video_path=args.video,
        calibration_path=None if args.no_runtime_calibration else args.calibration,
        model_path=args.model,
        yolo_confidence=args.yolo_confidence,
        event_track_max_age=args.event_track_max_age,
        event_track_min_frames=args.event_track_min_frames,
        event_track_min_travel_px=args.event_track_min_travel_px,
        event_count_debounce_sec=args.event_count_debounce_sec,
        event_track_max_match_distance=args.event_track_max_match_distance,
        event_detection_cluster_distance=args.event_detection_cluster_distance,
        playback_speed=args.playback_speed,
        processing_fps=args.processing_fps,
        reader_fps=args.reader_fps,
    )
    command = build_uvicorn_command(port=args.port)
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    main()
