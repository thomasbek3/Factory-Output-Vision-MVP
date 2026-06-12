from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_event_proposer import build_event_proposals, write_event_proposals
from app.services.station_calibration import read_station_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Propose onboarding event candidates from recorded segments")
    parser.add_argument("--segment-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--motion-threshold", type=float, default=0.025)
    parser.add_argument("--station-calibration", type=Path, default=None)
    parser.add_argument("--output-polygon", default=None, help="normalized output polygon JSON string")
    parser.add_argument("--proposal-mode", choices=["full_frame_motion", "output_zone_motion"], default="full_frame_motion")
    parser.add_argument("--zone-motion-threshold", type=float, default=0.04)
    parser.add_argument("--min-cluster-gap-sec", type=float, default=1.0)
    parser.add_argument("--window-before-sec", type=float, default=4.0)
    parser.add_argument("--window-after-sec", type=float, default=4.0)
    parser.add_argument("--stable-negative-count", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        output_zone_polygon = _load_output_zone_polygon(
            station_calibration=args.station_calibration,
            output_polygon_json=args.output_polygon,
        )
        payload = build_event_proposals(
            segment_manifest_path=args.segment_manifest,
            sample_fps=args.sample_fps,
            motion_threshold=args.motion_threshold,
            output_zone_polygon=output_zone_polygon,
            proposal_mode=args.proposal_mode,
            zone_motion_threshold=args.zone_motion_threshold,
            min_cluster_gap_sec=args.min_cluster_gap_sec,
            window_before_sec=args.window_before_sec,
            window_after_sec=args.window_after_sec,
            stable_negative_count=args.stable_negative_count,
        )
        write_event_proposals(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "proposal_count": payload["summary"]["proposal_count"],
                "event_proposal_count": payload["summary"]["event_proposal_count"],
                "stable_negative_count": payload["summary"]["stable_negative_count"],
            },
            sort_keys=True,
        )
    )
    return 0


def _load_output_zone_polygon(
    *,
    station_calibration: Path | None,
    output_polygon_json: str | None,
) -> list[list[float]] | None:
    if output_polygon_json is not None and station_calibration is not None:
        raise ValueError("--output-polygon and --station-calibration are mutually exclusive")
    if output_polygon_json is not None:
        return json.loads(output_polygon_json)
    if station_calibration is None:
        return None
    payload = read_station_calibration(station_calibration)
    output_polygons = payload.get("output_polygons") or []
    if not output_polygons:
        raise ValueError("station calibration must include at least one output polygon")
    return output_polygons[0]


if __name__ == "__main__":
    raise SystemExit(main())
