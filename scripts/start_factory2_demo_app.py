#!/usr/bin/env python3
"""Launch the verified Factory2 investor demo app configuration."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


DEFAULT_VIDEO_PATH = Path("data/videos/from-pc/factory2.MOV")
DEFAULT_CALIBRATION_PATH = Path("data/calibration/factory2_ai_only_v1.json")


def _stringify_number(value: float) -> str:
    return f"{value:g}"


def build_demo_env(
    *,
    base_env: dict[str, str] | None = None,
    video_path: Path = DEFAULT_VIDEO_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
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
            "FC_RUNTIME_CALIBRATION_PATH": str(calibration_path.resolve()),
            "FC_PROCESSING_FPS": _stringify_number(processing_fps),
            "FC_READER_FPS": _stringify_number(reader_fps),
        }
    )
    return env


def build_uvicorn_command(*, port: int) -> list[str]:
    return ["python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the verified Factory2 investor demo app")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_PATH)
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument("--processing-fps", type=float, default=10.0)
    parser.add_argument("--reader-fps", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = build_demo_env(
        video_path=args.video,
        calibration_path=args.calibration,
        playback_speed=args.playback_speed,
        processing_fps=args.processing_fps,
        reader_fps=args.reader_fps,
    )
    os.execvpe("python", build_uvicorn_command(port=args.port), env)


if __name__ == "__main__":
    main()
