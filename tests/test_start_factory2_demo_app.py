from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.start_factory2_demo_app import build_demo_env, build_uvicorn_command
from scripts.start_factory2_demo_stack import (
    _backend_command,
    _launch_process,
    build_frontend_command,
    build_frontend_env,
)


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
        model_path=Path("/tmp/custom.pt"),
        yolo_confidence=0.2,
        event_track_max_age=5,
        event_track_min_frames=4,
        event_track_min_travel_px=75.5,
        event_count_debounce_sec=30.0,
        event_track_max_match_distance=150.5,
        event_detection_cluster_distance=125.0,
        playback_speed=2.0,
        processing_fps=8.0,
        reader_fps=8.0,
    )

    assert env["FC_DEMO_VIDEO_PATH"] == str(Path("/tmp/custom.mov").resolve())
    assert env["FC_RUNTIME_CALIBRATION_PATH"] == str(Path("/tmp/custom.json").resolve())
    assert env["FC_YOLO_MODEL_PATH"] == str(Path("/tmp/custom.pt").resolve())
    assert env["FC_YOLO_CONF_THRESHOLD"] == "0.2"
    assert env["FC_YOLO_EXCLUDED_CLASSES"] == ""
    assert env["FC_EVENT_TRACK_MAX_AGE"] == "5"
    assert env["FC_EVENT_TRACK_MIN_FRAMES"] == "4"
    assert env["FC_EVENT_TRACK_MIN_TRAVEL_PX"] == "75.5"
    assert env["FC_EVENT_COUNT_DEBOUNCE_SEC"] == "30"
    assert env["FC_EVENT_TRACK_MAX_MATCH_DISTANCE"] == "150.5"
    assert env["FC_EVENT_DETECTION_CLUSTER_DISTANCE"] == "125"
    assert env["FC_DEMO_PLAYBACK_SPEED"] == "2"
    assert env["FC_PROCESSING_FPS"] == "8"
    assert env["FC_READER_FPS"] == "8"


def test_build_demo_env_can_disable_runtime_calibration() -> None:
    env = build_demo_env(
        base_env={"PATH": os.environ.get("PATH", "")},
        calibration_path=None,
    )

    assert env["FC_RUNTIME_CALIBRATION_PATH"] == ""


def test_build_uvicorn_command_uses_requested_port() -> None:
    command = build_uvicorn_command(port=8099)

    assert "8099" in command
    assert command[:4] == [sys.executable, "-m", "uvicorn", "app.main:app"]
    assert "--no-access-log" in command


def test_build_frontend_env_points_dev_server_at_backend_origin() -> None:
    env = build_frontend_env(
        base_env={"PATH": os.environ.get("PATH", "")},
        backend_port=8091,
    )

    assert env["VITE_API_BASE"] == ""
    assert env["VITE_BACKEND_ORIGIN"] == "http://127.0.0.1:8091"


def test_build_frontend_command_uses_requested_port() -> None:
    command = build_frontend_command(port=5179)

    assert command == ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5179"]


def test_stack_backend_command_passes_demo_overrides() -> None:
    command = _backend_command(
        port=8098,
        video=Path("demo/IMG_3262.MOV"),
        calibration=Path("data/calibration/custom.json"),
        model=Path("models/custom.pt"),
        yolo_confidence=0.2,
        event_track_max_age=5,
        event_track_min_frames=4,
        event_track_min_travel_px=75.5,
        event_count_debounce_sec=30.0,
        event_track_max_match_distance=150.5,
        event_detection_cluster_distance=125.0,
        playback_speed=1.0,
        processing_fps=12.5,
        reader_fps=12.5,
    )

    assert command[:3] == [sys.executable, "scripts/start_factory2_demo_app.py", "--port"]
    assert "8098" in command
    assert command[command.index("--video") + 1] == "demo/IMG_3262.MOV"
    assert command[command.index("--calibration") + 1] == "data/calibration/custom.json"
    assert command[command.index("--model") + 1] == "models/custom.pt"
    assert command[command.index("--yolo-confidence") + 1] == "0.2"
    assert command[command.index("--event-track-max-age") + 1] == "5"
    assert command[command.index("--event-track-min-frames") + 1] == "4"
    assert command[command.index("--event-track-min-travel-px") + 1] == "75.5"
    assert command[command.index("--event-count-debounce-sec") + 1] == "30"
    assert command[command.index("--event-track-max-match-distance") + 1] == "150.5"
    assert command[command.index("--event-detection-cluster-distance") + 1] == "125"
    assert command[command.index("--playback-speed") + 1] == "1"
    assert command[command.index("--processing-fps") + 1] == "12.5"
    assert command[command.index("--reader-fps") + 1] == "12.5"


def test_stack_backend_command_can_disable_runtime_calibration() -> None:
    command = _backend_command(
        port=8098,
        video=Path("demo/IMG_3262.MOV"),
        calibration=None,
        model=None,
        yolo_confidence=None,
        event_track_max_age=None,
        event_track_min_frames=None,
        event_track_min_travel_px=None,
        event_count_debounce_sec=None,
        event_track_max_match_distance=None,
        event_detection_cluster_distance=None,
        playback_speed=1.0,
        processing_fps=10,
        reader_fps=10,
    )

    assert "--no-runtime-calibration" in command
    assert "--calibration" not in command


def test_stack_launcher_closes_child_stdin(tmp_path: Path) -> None:
    fake_process = Mock()

    with patch("scripts.start_factory2_demo_stack.subprocess.Popen", return_value=fake_process) as popen:
        process = _launch_process(
            command=["npm", "run", "dev"],
            cwd=tmp_path,
            env={"PATH": os.environ.get("PATH", "")},
            log_path=tmp_path / "server.log",
        )

    assert process is fake_process
    assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL
    assert popen.call_args.kwargs["start_new_session"] is True
    popen.call_args.kwargs["stdout"].close()
