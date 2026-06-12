from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_rehearsal import (
    DEFAULT_STATIONS,
    SCHEMA_VERSION,
    assert_no_truth_leakage,
    build_scoreboard,
    build_station_stages,
    run_station,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the autonomous station-onboarding rehearsal: footage -> teacher -> boxes -> train -> holdout gate"
    )
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="scoreboard report path")
    parser.add_argument("--stations", default=None, help="comma-separated station_id filter (default: all four gold stations)")
    parser.add_argument("--teacher-provider", default="codex_cli")
    parser.add_argument("--allow-cloud", action="store_true")
    parser.add_argument("--teacher-batch-size", type=int, default=4)
    parser.add_argument("--box-backend", default="diff_box", choices=["diff_box", "yolo_world"])
    parser.add_argument("--base-model", type=Path, default=Path("yolov8n.pt"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--playback-speed", type=float, default=8.0)
    parser.add_argument("--train-gate-min-positive-ratio", type=float, default=0.8)
    parser.add_argument("--train-gate-max-hard-neg-fps", type=int, default=0)
    parser.add_argument("--enable-mining", action="store_true", help="opt-in self-correction round; unsafe below ~0.95 teacher recall")
    parser.add_argument("--force-stage", action="append", default=[], help="stage name to re-run even if its artifact exists")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    stations = DEFAULT_STATIONS
    if args.stations:
        wanted = {name.strip() for name in args.stations.split(",") if name.strip()}
        stations = [station for station in DEFAULT_STATIONS if station["station_id"] in wanted]
        if not stations:
            print(f"error: no stations matched {sorted(wanted)}", file=sys.stderr)
            return 1
    if args.output.exists() and not args.force:
        print(f"error: {args.output} exists; pass --force", file=sys.stderr)
        return 1

    force_stages = set(args.force_stage)
    config = {
        "teacher_provider": args.teacher_provider,
        "teacher_batch_size": args.teacher_batch_size,
        "box_backend": args.box_backend,
        "base_model": str(args.base_model),
        "epochs": args.epochs,
        "device": args.device,
        "playback_speed": args.playback_speed,
        "enable_mining": args.enable_mining,
        "train_gate": {
            "min_positive_ratio": args.train_gate_min_positive_ratio,
            "max_hard_negative_false_positives": args.train_gate_max_hard_neg_fps,
        },
        "force_stages": sorted(force_stages),
    }

    station_runs = []
    for station in stations:
        stages = build_station_stages(
            station,
            work_root=args.work_root,
            playback_speed=args.playback_speed,
            teacher_provider=args.teacher_provider,
            allow_cloud=args.allow_cloud,
            teacher_batch_size=args.teacher_batch_size,
            box_backend=args.box_backend,
            base_model=args.base_model,
            epochs=args.epochs,
            device=args.device,
            enable_mining=args.enable_mining,
        )
        assert_no_truth_leakage(stages, truth_ledger=station["truth_ledger"])
        print(json.dumps({"station": station["station_id"], "status": "starting"}), flush=True)
        run = run_station(station, stages=stages, force_stages=force_stages, device=args.device)
        station_runs.append(run)
        print(
            json.dumps(
                {
                    "station": station["station_id"],
                    "status": "failed_at_" + run["failed_stage"] if run["failed_stage"] else "completed",
                }
            ),
            flush=True,
        )

    scoreboard = build_scoreboard(
        stations=stations,
        station_runs=station_runs,
        work_root=args.work_root,
        config=config,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "schema_version": SCHEMA_VERSION,
                "stations": scoreboard["summary"]["station_count"],
                "gate_passed_count": scoreboard["summary"]["gate_passed_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
