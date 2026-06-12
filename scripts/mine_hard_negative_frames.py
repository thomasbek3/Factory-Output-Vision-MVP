from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.hard_negative_miner import mine_hard_negative_frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mine the v1 model's false positives in confirmed-negative train windows as hard negatives"
    )
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--model-report", type=Path, default=None, help="training report whose trained_model_path locates the model")
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--segment-manifest", type=Path, required=True)
    parser.add_argument("--base-hard-negative-export", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.2)
    parser.add_argument("--sample-fps", type=float, default=3.0)
    parser.add_argument("--max-mined-frames", type=int, default=80)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        if (args.model is None) == (args.model_report is None):
            raise ValueError("pass exactly one of --model or --model-report")
        model_path = args.model
        if model_path is None:
            report = json.loads(args.model_report.read_text(encoding="utf-8"))
            trained = report.get("trained_model_path")
            if not trained:
                raise ValueError(f"{args.model_report} has no trained_model_path")
            model_path = Path(trained)
        payload = mine_hard_negative_frames(
            model_path=model_path,
            teacher_labels_path=args.teacher_labels,
            segment_manifest_path=args.segment_manifest,
            base_hard_negative_export_path=args.base_hard_negative_export,
            work_dir=args.work_dir,
            output_export_path=args.output,
            confidence=args.confidence,
            sample_fps=args.sample_fps,
            max_mined_frames=args.max_mined_frames,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "mined_count": payload["mining"]["mined_count"],
                "base_negative_count": payload["mining"]["base_negative_count"],
                "total_negatives": payload["count"],
                "excluded_window_count": payload["mining"]["excluded_window_count"],
                "sampled_frames": payload["mining"]["sampled_frames"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
