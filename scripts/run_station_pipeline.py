"""One-command Track B onboarding: mine -> extract -> label -> train -> recall -> exam.

Thin CLI over app.services.station_pipeline. The stage graph is declarative;
this file only parses flags and prints results.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.station_pipeline import build_track_b_stages, run_station  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Track B clip-student onboarding pipeline for one station.",
    )
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True, help="station_calibration.json")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--labeler", choices=["codex", "human"], default="codex")
    parser.add_argument("--times", help="placement times for --labeler human (CSV or comma seconds)")
    parser.add_argument("--votes", type=int, default=1)
    parser.add_argument("--arch", default="stack3_mobilenet")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--trigger", choices=["person_presence", "pixel"], default="person_presence")
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--force-stage", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True, help="pipeline report JSON path")
    args = parser.parse_args(argv)

    stages = build_track_b_stages(
        station_id=args.station_id,
        video=args.video,
        calibration=args.calibration,
        work_root=args.work_root,
        labeler=args.labeler,
        label_votes=args.votes,
        placement_times=args.times,
        arch=args.arch,
        epochs=args.epochs,
        device=args.device,
        tripwire_trigger=args.trigger,
        match_tolerance_sec=args.match_tolerance_sec,
    )
    result = run_station(
        {"station_id": args.station_id, "video": str(args.video), "truth_ledger": ""},
        stages=stages,
        force_stages=set(args.force_stage),
        device=args.device,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("failed_stage") else 0


if __name__ == "__main__":
    raise SystemExit(main())
