from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.holdout_split import (
    GENERATED_BY,
    author_holdout_case_manifest,
    compute_holdout_split,
    cut_clips,
    derive_holdout_truth_ledger,
    probe_keyframes,
    probe_video,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Split a station video into a train clip and a derived holdout gate case"
    )
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--truth-ledger", type=Path, required=True, help="used ONLY for split selection and the derived gate ledger")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True, help="model the holdout gate case will run (the auto-trained station model)")
    parser.add_argument("--calibration-path", type=Path, default=None, help="auto-derived runtime calibration zones the gate case will load")
    parser.add_argument("--playback-speed", type=float, default=8.0)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--min-holdout-truth-events", type=int, default=3)
    parser.add_argument("--backend-port", type=int, default=8093)
    parser.add_argument("--frontend-port", type=int, default=5175)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        work_dir = args.work_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        video_info = probe_video(args.video)
        truth = json.loads(args.truth_ledger.read_text(encoding="utf-8"))
        timestamps = [float(event.get("event_ts") or 0.0) for event in truth.get("events") or []]
        keyframes = probe_keyframes(args.video)
        split = compute_holdout_split(
            duration_sec=float(video_info["duration_sec"]),
            truth_event_timestamps=timestamps,
            keyframes=keyframes,
            train_fraction=args.train_fraction,
            min_holdout_truth_events=args.min_holdout_truth_events,
        )
        suffix = args.video.suffix or ".mp4"
        train_clip = work_dir / f"{args.station_id}_train{suffix}"
        holdout_clip = work_dir / f"{args.station_id}_holdout{suffix}"
        cut_report = cut_clips(
            video_path=args.video,
            split_sec=split["split_sec"],
            train_clip_path=train_clip,
            holdout_clip_path=holdout_clip,
            force=args.force,
        )
        ledger_path = work_dir / f"{args.station_id}_holdout_truth_ledger.json"
        ledger = derive_holdout_truth_ledger(
            source_ledger_path=args.truth_ledger,
            split_sec=split["split_sec"],
            output_path=ledger_path,
            force=args.force,
        )
        manifest_path = work_dir / f"{args.station_id}_holdout_case_manifest.json"
        author_holdout_case_manifest(
            station_id=args.station_id,
            holdout_clip_path=holdout_clip,
            derived_ledger=ledger,
            derived_ledger_path=ledger_path,
            model_path=args.model_path,
            runtime_calibration_path=args.calibration_path,
            playback_speed=args.playback_speed,
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            output_path=manifest_path,
            force=args.force,
        )
        split_report_path = work_dir / f"{args.station_id}_split_report.json"
        split_report = {
            "schema_version": "factory-vision-holdout-split-report-v1",
            "generated_by": GENERATED_BY,
            "source_video": video_info,
            "split": split,
            "cut": cut_report,
            "truth_timestamp_touch": "split_selection_only",
            "train_clip_path": str(train_clip),
            "holdout_clip_path": str(holdout_clip),
            "holdout_truth_ledger_path": str(ledger_path),
            "holdout_case_manifest_path": str(manifest_path),
        }
        if split_report_path.exists() and not args.force:
            raise FileExistsError(split_report_path)
        split_report_path.write_text(json.dumps(split_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "split_report": split_report_path.as_posix(),
                "split_sec": split["split_sec"],
                "adjusted": split["adjusted"],
                "holdout_truth_event_count": split["holdout_truth_event_count"],
                "train_clip": train_clip.as_posix(),
                "holdout_case_manifest": manifest_path.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
