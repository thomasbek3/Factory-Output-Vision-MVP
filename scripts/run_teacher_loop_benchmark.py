from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_loop_benchmark import build_teacher_loop_benchmark, write_teacher_loop_benchmark


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark teacher verification loop against no-teacher baseline")
    parser.add_argument("--event-proposals", type=Path, required=True)
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--fusion-report", type=Path, required=True)
    parser.add_argument("--min-silver-candidates", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_teacher_loop_benchmark(
            event_proposals_path=args.event_proposals,
            teacher_labels_path=args.teacher_labels,
            fusion_report_path=args.fusion_report,
            min_silver_candidates=args.min_silver_candidates,
        )
        write_teacher_loop_benchmark(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "status": payload["benchmark_gate"]["status"],
                "teacher_beats_no_teacher_baseline": payload["benchmark_gate"][
                    "teacher_beats_no_teacher_baseline"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
