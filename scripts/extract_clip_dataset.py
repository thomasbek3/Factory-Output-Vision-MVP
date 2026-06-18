#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.clip_dataset import extract_clip_dataset, load_candidates, output_zone_from_calibration, write_clip_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Day-4 placement action clip samples from tripwire candidates.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--video", type=Path, help="Default source video when candidates do not carry a source path.")
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--encoding", choices=["stack3", "clip", "flow", "all"], default="clip")
    parser.add_argument("--clip-fps", type=float, default=6.0)
    parser.add_argument("--clip-frames", type=int, default=16)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    manifest = extract_clip_dataset(
        candidates=load_candidates(args.candidates),
        output_dir=args.out_dir,
        output_zone_polygon=output_zone_from_calibration(args.station_calibration),
        default_video_path=args.video,
        encoding=args.encoding,
        clip_fps=args.clip_fps,
        clip_frame_count=args.clip_frames,
    )
    write_clip_manifest(args.manifest_out, manifest, force=args.force)
    print(json.dumps({"sample_count": len(manifest["samples"]), "manifest": str(args.manifest_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
