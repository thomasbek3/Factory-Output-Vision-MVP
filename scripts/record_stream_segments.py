#!/usr/bin/env python3
"""Record an RTSP/file source into replayable Factory Vision segment artifacts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.stream_recorder import StreamSegmentRecorder


def default_recording_root() -> Path:
    raw = os.getenv("FC_ARTIFACT_ROOT", "/Users/thomas/FactoryVisionArtifacts")
    return Path(raw).expanduser().resolve() / "recordings"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record RTSP/file video into rolling local segments")
    parser.add_argument("--source", required=True, help="RTSP URL or local video path")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--output-root", type=Path, default=default_recording_root())
    parser.add_argument("--segment-seconds", type=int, default=60)
    parser.add_argument("--retention-minutes", type=int, default=30)
    parser.add_argument("--container", default="mkv", choices=["mkv", "mp4", "ts"])
    parser.add_argument("--duration-sec", type=float, help="Optional max runtime; useful for tests/file smoke runs")
    parser.add_argument("--realtime-file-input", action="store_true", help="Throttle local file input with ffmpeg -re")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        recorder = StreamSegmentRecorder(
            source=args.source,
            station_id=args.station_id,
            output_root=args.output_root,
            segment_seconds=args.segment_seconds,
            retention_minutes=args.retention_minutes,
            container=args.container,
            realtime_file_input=args.realtime_file_input,
        )
        result = recorder.run(duration_sec=args.duration_sec)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    valid_stop = (result.get("timed_out") or result.get("interrupted")) and result.get("new_valid_segment_count", 0) > 0
    if result.get("returncode") not in (0, None) and not valid_stop:
        print(f"error: ffmpeg exited with code {result.get('returncode')}", file=sys.stderr)
        return 1
    if result.get("new_valid_segment_count", 0) <= 0:
        print("error: no new valid segments recorded", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
