#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.zone_tripwire import (
    TripwireConfig,
    load_output_zone_polygon,
    run_tripwire_on_segment_manifest,
    run_tripwire_on_video,
    write_tripwire_payload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Day-4 zone Tripwire v2 over a video or segment manifest.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--segment-manifest", type=Path)
    source.add_argument("--video", type=Path)
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--grid-size", type=int, default=8)
    parser.add_argument("--score-method", choices=["tiled_absdiff", "tiled_ssim", "tiled_edge"], default="tiled_absdiff")
    parser.add_argument("--burst-threshold", type=float, default=0.10)
    parser.add_argument("--state-interval", type=float, default=3.0)
    parser.add_argument("--calm-threshold", type=float, default=0.015)
    parser.add_argument("--state-threshold", type=float, default=0.06)
    parser.add_argument("--min-flash-ratio", type=float, default=1.5)
    parser.add_argument("--bracket-sec", type=float, default=8.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    config = TripwireConfig(
        sample_fps=args.sample_fps,
        grid_size=args.grid_size,
        score_method=args.score_method,
        burst_threshold=args.burst_threshold,
        state_interval_sec=args.state_interval,
        calm_threshold=args.calm_threshold,
        state_threshold=args.state_threshold,
        min_flash_ratio=args.min_flash_ratio,
        bracket_sec=args.bracket_sec,
    )
    polygon = load_output_zone_polygon(args.station_calibration)
    if args.video is not None:
        payload = run_tripwire_on_video(video_path=args.video, output_zone_polygon=polygon, config=config)
    else:
        payload = run_tripwire_on_segment_manifest(
            segment_manifest_path=args.segment_manifest,
            output_zone_polygon=polygon,
            config=config,
        )
    payload["cli"] = {"config": asdict(config), "station_calibration": str(args.station_calibration)}
    write_tripwire_payload(args.out, payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
