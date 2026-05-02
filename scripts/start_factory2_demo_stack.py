#!/usr/bin/env python3
"""Start the verified Factory2 investor demo backend and frontend together."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = REPO_ROOT / "data" / "logs"


def build_frontend_env(*, base_env: dict[str, str] | None = None, backend_port: int) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    backend_origin = f"http://127.0.0.1:{backend_port}"
    env["VITE_API_BASE"] = ""
    env["VITE_BACKEND_ORIGIN"] = backend_origin
    return env


def build_frontend_command(*, port: int) -> list[str]:
    return ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]


def _backend_command(
    *,
    port: int,
    video: Path,
    calibration: Path | None,
    model: Path | None,
    yolo_confidence: float | None,
    event_track_max_age: int | None,
    event_track_min_frames: int | None,
    event_track_max_match_distance: float | None,
    event_detection_cluster_distance: float | None,
    playback_speed: float,
    processing_fps: float,
    reader_fps: float,
) -> list[str]:
    command = [
        os.sys.executable,
        "scripts/start_factory2_demo_app.py",
        "--port",
        str(port),
        "--video",
        str(video),
        "--playback-speed",
        f"{playback_speed:g}",
        "--processing-fps",
        f"{processing_fps:g}",
        "--reader-fps",
        f"{reader_fps:g}",
    ]
    if calibration is None:
        command.append("--no-runtime-calibration")
    else:
        command.extend(["--calibration", str(calibration)])
    if model is not None:
        command.extend(["--model", str(model)])
    if yolo_confidence is not None:
        command.extend(["--yolo-confidence", f"{yolo_confidence:g}"])
    if event_track_max_age is not None:
        command.extend(["--event-track-max-age", str(event_track_max_age)])
    if event_track_min_frames is not None:
        command.extend(["--event-track-min-frames", str(event_track_min_frames)])
    if event_track_max_match_distance is not None:
        command.extend(["--event-track-max-match-distance", f"{event_track_max_match_distance:g}"])
    if event_detection_cluster_distance is not None:
        command.extend(["--event-detection-cluster-distance", f"{event_detection_cluster_distance:g}"])
    return command


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Factory2 investor demo backend and frontend")
    parser.add_argument("--backend-port", type=int, default=8091)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--video", type=Path, default=Path("data/videos/from-pc/factory2.MOV"))
    parser.add_argument("--calibration", type=Path, default=Path("data/calibration/factory2_ai_only_v1.json"))
    parser.add_argument("--no-runtime-calibration", action="store_true")
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--yolo-confidence", type=float, default=None)
    parser.add_argument("--event-track-max-age", type=int, default=None)
    parser.add_argument("--event-track-min-frames", type=int, default=None)
    parser.add_argument("--event-track-max-match-distance", type=float, default=None)
    parser.add_argument("--event-detection-cluster-distance", type=float, default=None)
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument("--processing-fps", type=float, default=10.0)
    parser.add_argument("--reader-fps", type=float, default=10.0)
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-port-cleanup", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=90.0)
    return parser.parse_args()


def _pids_listening_on_port(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _wait_for_port_to_clear(port: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pids_listening_on_port(port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Port {port} is still occupied after waiting {timeout:.1f}s")


def _terminate_processes_on_port(port: int) -> None:
    pids = _pids_listening_on_port(port)
    if not pids:
        return
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    try:
        _wait_for_port_to_clear(port, timeout=5.0)
        return
    except RuntimeError:
        pass
    for pid in _pids_listening_on_port(port):
        os.kill(pid, signal.SIGKILL)
    _wait_for_port_to_clear(port, timeout=5.0)


def _wait_for_http_ready(url: str, *, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if 200 <= response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _launch_process(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def main() -> None:
    args = _parse_args()
    backend_port = args.backend_port
    frontend_port = args.frontend_port

    if not args.skip_port_cleanup:
        _terminate_processes_on_port(backend_port)
        if not args.skip_frontend:
            _terminate_processes_on_port(frontend_port)

    backend_log = args.logs_dir / f"factory2_demo_backend_{backend_port}.log"
    backend_process = _launch_process(
        command=_backend_command(
            port=backend_port,
            video=args.video,
            calibration=None if args.no_runtime_calibration else args.calibration,
            model=args.model,
            yolo_confidence=args.yolo_confidence,
            event_track_max_age=args.event_track_max_age,
            event_track_min_frames=args.event_track_min_frames,
            event_track_max_match_distance=args.event_track_max_match_distance,
            event_detection_cluster_distance=args.event_detection_cluster_distance,
            playback_speed=args.playback_speed,
            processing_fps=args.processing_fps,
            reader_fps=args.reader_fps,
        ),
        cwd=REPO_ROOT,
        env=dict(os.environ),
        log_path=backend_log,
    )
    _wait_for_http_ready(f"http://127.0.0.1:{backend_port}/api/status", timeout=args.startup_timeout)

    frontend_process: subprocess.Popen[bytes] | None = None
    frontend_log: Path | None = None
    if not args.skip_frontend:
        frontend_log = args.logs_dir / f"factory2_demo_frontend_{frontend_port}.log"
        frontend_process = _launch_process(
            command=build_frontend_command(port=frontend_port),
            cwd=REPO_ROOT / "frontend",
            env=build_frontend_env(base_env=dict(os.environ), backend_port=backend_port),
            log_path=frontend_log,
        )
        _wait_for_http_ready(f"http://127.0.0.1:{frontend_port}/dashboard", timeout=args.startup_timeout)

    print(f"Backend PID: {backend_process.pid}")
    print(f"Backend URL: http://127.0.0.1:{backend_port}/dashboard")
    print(f"Backend log: {backend_log}")
    print(f"Demo video: {args.video}")
    if frontend_process is not None and frontend_log is not None:
        print(f"Frontend PID: {frontend_process.pid}")
        print(f"Frontend URL: http://127.0.0.1:{frontend_port}/dashboard")
        print(f"Frontend log: {frontend_log}")


if __name__ == "__main__":
    main()
