from __future__ import annotations

import os
from pathlib import Path

from scripts.start_factory2_demo_app import build_demo_env, build_uvicorn_command


def test_build_demo_env_sets_verified_factory2_defaults() -> None:
    env = build_demo_env(base_env={"PATH": os.environ.get("PATH", "")})

    assert env["FC_DEMO_MODE"] == "1"
    assert env["FC_DEMO_LOOP"] == "0"
    assert env["FC_DEMO_COUNT_MODE"] == "live_reader_snapshot"
    assert env["FC_COUNTING_MODE"] == "event_based"
    assert env["FC_RUNTIME_CALIBRATION_PATH"].endswith("data/calibration/factory2_ai_only_v1.json")
    assert env["FC_DEMO_VIDEO_PATH"].endswith("data/videos/from-pc/factory2.MOV")
    assert env["FC_PROCESSING_FPS"] == "10"
    assert env["FC_READER_FPS"] == "10"


def test_build_demo_env_allows_overrides() -> None:
    env = build_demo_env(
        base_env={"PATH": os.environ.get("PATH", "")},
        video_path=Path("/tmp/custom.mov"),
        calibration_path=Path("/tmp/custom.json"),
        playback_speed=2.0,
        processing_fps=8.0,
        reader_fps=8.0,
    )

    assert env["FC_DEMO_VIDEO_PATH"] == str(Path("/tmp/custom.mov").resolve())
    assert env["FC_RUNTIME_CALIBRATION_PATH"] == str(Path("/tmp/custom.json").resolve())
    assert env["FC_DEMO_PLAYBACK_SPEED"] == "2"
    assert env["FC_PROCESSING_FPS"] == "8"
    assert env["FC_READER_FPS"] == "8"


def test_build_uvicorn_command_uses_requested_port() -> None:
    command = build_uvicorn_command(port=8099)

    assert command[-1] == "8099"
    assert command[:4] == ["python", "-m", "uvicorn", "app.main:app"]
